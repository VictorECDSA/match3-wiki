"""
UI detection for Candy Crush Saga bot using OpenCV template matching.

Replaces the fragile pixel-coordinate heuristics in screen_detector.py with
robust template matching that works regardless of exact dialog position.

Screen states:
  MAP         - world map / level select view
  PRE_PLAY    - level info dialog ("Play!" button visible)
  PLAYING     - active gameplay board
  COMPLETE    - level complete result screen
  FAILED      - level failed result screen
  UNKNOWN     - none of the above (loading, transition, popup)
"""

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREEN_W = 1220
SCREEN_H = 2712

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Screen state strings
MAP      = "map"
PRE_PLAY = "pre_play"
PLAYING  = "playing"
COMPLETE = "complete"
FAILED   = "failed"
UNKNOWN  = "unknown"

# Minimum confidence for template match to count
_MATCH_THRESHOLD = 0.75


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pil_to_cv(img: Image.Image) -> np.ndarray:
    """Convert PIL RGBA/RGB image to OpenCV BGR uint8 array."""
    arr = np.array(img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _load_template(name: str) -> np.ndarray:
    """Load a template image from templates/ as a BGR OpenCV array."""
    path = TEMPLATES_DIR / name
    tmpl = cv2.imread(str(path))
    if tmpl is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return tmpl


# cache templates so we don't re-read from disk every frame
_template_cache: dict[str, np.ndarray] = {}


def _get_template(name: str) -> np.ndarray:
    if name not in _template_cache:
        _template_cache[name] = _load_template(name)
    return _template_cache[name]


def find_template(
    screen_img: Image.Image,
    template_name: str,
    threshold: float = _MATCH_THRESHOLD,
    search_region: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, float] | None:
    """
    Find template_name in screen_img using normalised cross-correlation.

    Args:
        screen_img:     Full-screen PIL image.
        template_name:  Filename inside templates/ (e.g. "btn_play.png").
        threshold:      Minimum match confidence [0, 1].
        search_region:  (x, y, w, h) to restrict search. None = full screen.

    Returns:
        (cx, cy, confidence) of the best match centre, or None if below threshold.
    """
    screen_bgr = _pil_to_cv(screen_img)
    tmpl = _get_template(template_name)
    th, tw = tmpl.shape[:2]

    if search_region is not None:
        rx, ry, rw, rh = search_region
        roi = screen_bgr[ry : ry + rh, rx : rx + rw]
    else:
        roi = screen_bgr
        rx, ry = 0, 0

    result = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < threshold:
        return None

    cx = rx + max_loc[0] + tw // 2
    cy = ry + max_loc[1] + th // 2
    return cx, cy, float(max_val)


# ---------------------------------------------------------------------------
# Board-area detection (green background strip above board)
# ---------------------------------------------------------------------------

def _is_playing(screen_bgr: np.ndarray) -> bool:
    """
    Check whether the active gameplay board is visible.

    Different levels use different board background themes (e.g. cyan teal for
    early levels, dark olive-green for later levels).  We cover all themes by
    using a broad hue range (H=75-130, covering teal through dark green) and
    scanning the full game area (y=200-2500) row-by-row.  If any row exceeds
    35 % coverage, the board background is on-screen.  The world map grass
    (H≈73-74) falls below this threshold.

    Side-panel overlays (e.g. the device's "game centre" panel) slide in from
    the left and cover roughly x=0-1000.  To remain robust we also check the
    right-side strip (x=900-1220) with a lower threshold (15 %), so a partially
    obscured board is still recognised as PLAYING.
    """
    h = screen_bgr.shape[0]
    region = screen_bgr[200:min(2500, h), :, :]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    # Broad game-board color range: teal / cyan-green / dark olive
    mask = cv2.inRange(hsv,
                       np.array([75, 50, 60]),
                       np.array([130, 255, 255]))
    # Full-width check: any row exceeds 35 % coverage
    row_sums = mask.sum(axis=1) / (mask.shape[1] * 255.0)
    if row_sums.max() > 0.35:
        return True
    # Right-strip check: side-panel overlays leave the right ~250 px uncovered.
    # If any row in that strip exceeds 15 % we still count it as PLAYING.
    right_strip = mask[:, 900:]
    if right_strip.shape[1] > 0:
        right_sums = right_strip.sum(axis=1) / (right_strip.shape[1] * 255.0)
        if right_sums.max() > 0.15:
            return True
    return False


# ---------------------------------------------------------------------------
# Level-complete / failed detection via colour region analysis
# ---------------------------------------------------------------------------

def _is_complete(screen_bgr: np.ndarray) -> bool:
    """Golden-yellow banner across top → level complete."""
    top = screen_bgr[80:220, 150:1070]
    hsv = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)
    # Gold: H≈20-35, S>100, V>150
    mask = cv2.inRange(hsv,
                       np.array([18, 100, 140]),
                       np.array([38, 255, 255]))
    gold_frac = mask.sum() / (mask.shape[0] * mask.shape[1] * 255)
    return gold_frac > 0.15


def _is_failed(screen_bgr: np.ndarray) -> bool:
    """
    Level-failed screen has a large dark overlay + a reddish/orange retry button.
    Check for prominent orange in the centre of the screen.
    """
    mid = screen_bgr[1600:1900, 200:1020]
    hsv = cv2.cvtColor(mid, cv2.COLOR_BGR2HSV)
    # Orange: H≈10-22, S>140, V>140
    mask = cv2.inRange(hsv,
                       np.array([8, 120, 120]),
                       np.array([24, 255, 255]))
    orange_frac = mask.sum() / (mask.shape[0] * mask.shape[1] * 255)
    return orange_frac > 0.12


# ---------------------------------------------------------------------------
# Map detection
# ---------------------------------------------------------------------------

def _is_map(screen_bgr: np.ndarray) -> bool:
    """
    World map: has a green grass background, no board teal strip, no dialog.
    Check for large green region in the middle of the screen.
    """
    mid = screen_bgr[600:1800, 0:1220]
    hsv = cv2.cvtColor(mid, cv2.COLOR_BGR2HSV)
    # Grass green: H≈60-90 (OpenCV), S>40, V>80
    mask = cv2.inRange(hsv,
                       np.array([55, 35, 70]),
                       np.array([95, 255, 255]))
    green_frac = mask.sum() / (mask.shape[0] * mask.shape[1] * 255)
    return green_frac > 0.10


# ---------------------------------------------------------------------------
# Main detect function
# ---------------------------------------------------------------------------

def detect_screen(img: Image.Image) -> str:
    """
    Detect the current game screen state.

    Detection order (most specific first):
      1. PRE_PLAY  - Play! button template found
      2. COMPLETE  - gold banner at top
      3. FAILED    - orange retry button area
      4. PLAYING   - teal board background strip
      5. MAP       - green map background
      6. UNKNOWN
    """
    screen_bgr = _pil_to_cv(img)

    # 1. Pre-play dialog: look for Play! button template
    if find_template(img, "btn_play.png", threshold=0.75) is not None:
        return PRE_PLAY

    # 2. Level complete
    if _is_complete(screen_bgr):
        return COMPLETE

    # 3. Level failed
    if _is_failed(screen_bgr):
        return FAILED

    # 4. Active board
    if _is_playing(screen_bgr):
        return PLAYING

    # 5. World map
    if _is_map(screen_bgr):
        return MAP

    return UNKNOWN


# ---------------------------------------------------------------------------
# UI action helpers
# ---------------------------------------------------------------------------

def find_play_button(img: Image.Image) -> tuple[int, int] | None:
    """Return (x, y) centre of the Play! button, or None if not found."""
    match = find_template(img, "btn_play.png", threshold=0.75)
    if match:
        return match[0], match[1]
    return None


def find_close_button(img: Image.Image) -> tuple[int, int] | None:
    """Return (x, y) centre of the X close button, or None if not found."""
    match = find_template(img, "btn_close.png", threshold=0.70)
    if match:
        return match[0], match[1]
    return None


# ---------------------------------------------------------------------------
# Level bubble detection on the map
# ---------------------------------------------------------------------------

def find_level_bubbles(img: Image.Image) -> list[tuple[int, int, int]]:
    """
    Find level number bubbles on the world map using circle detection.

    Returns list of (x, y, radius) for detected circular bubbles,
    sorted top-to-bottom (higher y = lower on screen = earlier level).
    """
    bgr = _pil_to_cv(img)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Detect circles (level bubbles are ~60-80px radius at 1220x2712)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=80,
        param1=60,
        param2=35,
        minRadius=40,
        maxRadius=90,
    )

    if circles is None:
        return []

    result = []
    for x, y, r in circles[0]:
        result.append((int(x), int(y), int(r)))

    # Sort by y descending (bottom of screen = earlier levels)
    result.sort(key=lambda b: -b[1])
    return result


def read_bubble_number(img: Image.Image, cx: int, cy: int, radius: int) -> int | None:
    """
    Read the level number from a bubble centred at (cx, cy) with given radius.
    Uses simple white-pixel digit recognition via connected components on the
    bright region inside the circle.

    Returns integer level number, or None if unreadable.
    """
    try:
        import pytesseract  # optional dependency
        pad = radius + 10
        crop = img.crop((cx - pad, cy - pad, cx + pad, cy + pad))
        # Convert to greyscale, threshold for white text
        g = np.array(crop.convert("L"))
        _, thresh = cv2.threshold(g, 180, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(
            thresh, config="--psm 10 -c tessedit_char_whitelist=0123456789"
        ).strip()
        if text.isdigit():
            return int(text)
    except ImportError:
        pass
    except Exception:
        pass
    return None


def find_latest_level_tap(img: Image.Image) -> tuple[int, int] | None:
    """
    Find the latest (highest-numbered) accessible level bubble on the map
    and return its (x, y) tap coordinates.

    Strategy:
      - The character avatar is always standing on the latest unlocked level.
      - The avatar is identified by scanning for the blue square frame
        (friend avatar indicator with red exclamation badge) near a bubble.
      - Fall back to the topmost bubble in the upper-third of the screen.
    """
    bgr = _pil_to_cv(img)

    # Look for the blue-bordered character frame (roughly 90x90 px blue square)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Blue frame: H≈100-125, S>80, V>80
    blue_mask = cv2.inRange(hsv,
                             np.array([95, 70, 70]),
                             np.array([130, 255, 255]))
    # Find largest blue contour
    contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_contour = None
    best_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if 3000 < area < 30000 and area > best_area:
            best_area = area
            best_contour = c

    if best_contour is not None:
        M = cv2.moments(best_contour)
        if M["m00"] > 0:
            avatar_x = int(M["m10"] / M["m00"])
            avatar_y = int(M["m01"] / M["m00"])

            # The current level bubble is the dark-purple circle nearest to the avatar
            bubbles = find_level_bubbles(img)
            if bubbles:
                closest = min(bubbles,
                              key=lambda b: (b[0] - avatar_x) ** 2 + (b[1] - avatar_y) ** 2)
                return closest[0], closest[1]

    # Fallback: pick the topmost bubble in the top third of the screen
    # (topmost = latest level since map scrolls with newest at top)
    bubbles = find_level_bubbles(img)
    if bubbles:
        top_third = [b for b in bubbles if b[1] < SCREEN_H // 3]
        if top_third:
            best = min(top_third, key=lambda b: b[1])
            return best[0], best[1]
        # If no bubble in top third, take the one with smallest y
        best = min(bubbles, key=lambda b: b[1])
        return best[0], best[1]

    return None
