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

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREEN_W = 1220
SCREEN_H = 2712

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

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

    The board background spans many rows continuously (teal/cyan-green/dark
    olive, H=75-130).  A title-screen globe or small decorative element may
    trigger one or two high-coverage rows but NOT a long consecutive run.

    We require at least MIN_CONSECUTIVE_ROWS rows in a row that each exceed
    ROW_THRESHOLD coverage — this rejects the title-screen globe (which
    triggers only a handful of rows) while accepting the real board (which
    spans ~600+ px / hundreds of rows).

    Side-panel overlays are handled by also checking the right-side strip
    (x=900-1220) with a slightly lower threshold.

    Guard: if the bottom navigation bar is present (white/cream bar at
    y=2550-2700, unique to the world-map screen), return False immediately.
    This prevents the map's green grass from being misidentified as the board.
    """
    h = screen_bgr.shape[0]

    # --- Map navigation-bar guard -------------------------------------------
    # The world-map screen has a white/cream bottom nav bar (~y=2550-2700).
    # During actual gameplay this region is dark (part of the board/UI).
    # A high fraction of near-white pixels means we are on the map, not playing.
    nav_y0 = min(2550, h - 10)
    nav_y1 = min(2700, h)
    if nav_y1 > nav_y0:
        bottom = screen_bgr[nav_y0:nav_y1, 100:1120]
        hsv_bottom = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
        nav_mask = cv2.inRange(hsv_bottom,
                               np.array([0,   0, 180]),
                               np.array([180, 60, 255]))
        nav_frac = nav_mask.sum() / (nav_mask.shape[0] * nav_mask.shape[1] * 255)
        if nav_frac > 0.25:
            return False
    # ------------------------------------------------------------------------

    MIN_CONSECUTIVE_ROWS = 40   # real board spans many rows; globe does not
    ROW_THRESHOLD        = 0.35
    STRIP_THRESHOLD      = 0.50  # raised: map purple trees reach ~0.55 on narrow strip

    region = screen_bgr[200:min(2500, h), :, :]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,
                       np.array([75, 50, 60]),
                       np.array([130, 255, 255]))

    # Full-width consecutive-row check
    row_sums = mask.sum(axis=1) / (mask.shape[1] * 255.0)
    consecutive = 0
    for v in row_sums:
        if v > ROW_THRESHOLD:
            consecutive += 1
            if consecutive >= MIN_CONSECUTIVE_ROWS:
                return True
        else:
            consecutive = 0

    # Right-strip consecutive-row check (handles side-panel overlays)
    right_strip = mask[:, 900:]
    if right_strip.shape[1] > 0:
        right_sums = right_strip.sum(axis=1) / (right_strip.shape[1] * 255.0)
        consecutive = 0
        for v in right_sums:
            if v > STRIP_THRESHOLD:
                consecutive += 1
                if consecutive >= MIN_CONSECUTIVE_ROWS:
                    return True
            else:
                consecutive = 0

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
    Level-failed screen: check for the Retry button in the lower-middle area.
    The button is hot-pink/magenta (H≈140-175) on some device themes, or
    orange (H≈8-24) on others.  Accept either.
    """
    mid = screen_bgr[1600:1950, 200:1020]
    hsv = cv2.cvtColor(mid, cv2.COLOR_BGR2HSV)
    # Orange retry button: H≈8-24, S>120, V>120
    mask_orange = cv2.inRange(hsv,
                               np.array([8, 120, 120]),
                               np.array([24, 255, 255]))
    orange_frac = mask_orange.sum() / (mid.shape[0] * mid.shape[1] * 255)
    if orange_frac > 0.12:
        return True
    # Hot-pink / magenta retry button: H≈140-175, S>80, V>100
    mask_pink = cv2.inRange(hsv,
                             np.array([140, 80, 100]),
                             np.array([175, 255, 255]))
    pink_frac = mask_pink.sum() / (mid.shape[0] * mid.shape[1] * 255)
    return pink_frac > 0.12


# ---------------------------------------------------------------------------
# Map detection
# ---------------------------------------------------------------------------

def _is_map(screen_bgr: np.ndarray) -> bool:
    """
    World map detection using the winding beige/tan path that runs through
    the centre of every world-map screen.

    The path has a distinctive warm beige colour (H≈10-40, S≈15-130, V>140)
    that covers >15% of the screen centre (y=600-1800, x=200-1020).
    This signal is absent on the gameplay board or any dialog.

    Fallback: also check for the large pink/magenta level-number bubbles
    (H≈140-175) which are unique to the world map.
    """
    mid = screen_bgr[600:1800, 200:1020]
    hsv = cv2.cvtColor(mid, cv2.COLOR_BGR2HSV)

    # Beige/tan winding path: H≈10-40, low-medium S, high V
    beige_mask = cv2.inRange(hsv,
                              np.array([10, 15, 140]),
                              np.array([40, 130, 255]))
    beige_frac = beige_mask.sum() / (mid.shape[0] * mid.shape[1] * 255)
    if beige_frac > 0.15:
        return True

    # Pink/magenta level bubbles: H≈140-175, S>80, V>100
    bubble_mask = cv2.inRange(hsv,
                               np.array([140, 80, 100]),
                               np.array([175, 255, 255]))
    bubble_frac = bubble_mask.sum() / (mid.shape[0] * mid.shape[1] * 255)
    return bubble_frac > 0.05


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
      4. MAP       - beige path / pink bubbles (checked BEFORE playing to avoid
                     the map's decorative purple trees triggering _is_playing)
      5. PLAYING   - teal board background strip
      6. UNKNOWN
    """
    screen_bgr = _pil_to_cv(img)

    # 1. Pre-play: level-entry "Play!" button OR title-screen "Play" button
    if find_template(img, "btn_play.png", threshold=0.75) is not None:
        return PRE_PLAY
    if find_template(img, "btn_play_title.png", threshold=0.70) is not None:
        return PRE_PLAY

    # 2. Level complete
    if _is_complete(screen_bgr):
        return COMPLETE

    # 3. Level failed
    if _is_failed(screen_bgr):
        return FAILED

    # 4. World map  ← must come BEFORE _is_playing
    if _is_map(screen_bgr):
        return MAP

    # 5. Active board
    if _is_playing(screen_bgr):
        return PLAYING

    return UNKNOWN


# ---------------------------------------------------------------------------
# UI action helpers
# ---------------------------------------------------------------------------

def find_play_button(img: Image.Image) -> tuple[int, int] | None:
    """Return (x, y) centre of the Play button (level-entry or title screen)."""
    match = find_template(img, "btn_play.png", threshold=0.75)
    if match:
        return match[0], match[1]
    match = find_template(img, "btn_play_title.png", threshold=0.70)
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


def find_real_level_bubbles(img: Image.Image) -> list[tuple[int, int, int]]:
    """
    Find actual level-number bubbles on the world map.

    Level bubbles are pink/magenta circles (H≈140-175 in OpenCV HSV).
    Uses HoughCircles then filters by colour to eliminate noise.

    Returns list of (x, y, radius) sorted top-to-bottom (smallest y first =
    newest level at top of map).
    """
    bgr = _pil_to_cv(img)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=120,
        param1=80,
        param2=40,
        minRadius=45,
        maxRadius=80,
    )
    if circles is None:
        return []

    result = []
    h = bgr.shape[0]
    for x, y, r in circles[0]:
        x, y, r = int(x), int(y), int(r)
        # Restrict to map content area (exclude nav bar and title)
        if not (400 < y < h - 200):
            continue
        # Check that the centre patch is pink/magenta
        py0, py1 = max(0, y - 20), min(h, y + 20)
        px0, px1 = max(0, x - 20), min(bgr.shape[1], x + 20)
        patch = bgr[py0:py1, px0:px1]
        if patch.size == 0:
            continue
        hsv_p = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        pink_m = cv2.inRange(hsv_p,
                              np.array([140, 80, 100]),
                              np.array([175, 255, 255]))
        pink_frac = pink_m.sum() / (patch.shape[0] * patch.shape[1] * 255)
        if pink_frac > 0.15:
            result.append((x, y, r))

    # Sort top-to-bottom (smallest y = newest level at top of scrolled map)
    result.sort(key=lambda b: b[1])
    return result


def needs_map_scroll(img: Image.Image) -> bool:
    """
    Return True if the map needs to be scrolled upward to reveal the latest level.

    The world map scrolls vertically with the newest (highest-numbered) level
    at the top.  We consider the map "fully scrolled to the top" only when the
    topmost pink bubble is within the upper 25% of the screen (y < SCREEN_H*0.25).
    If it is lower than that, there are likely more levels above the fold.
    """
    bubbles = find_real_level_bubbles(img)
    if not bubbles:
        # No bubbles at all — scroll up to try
        return True
    topmost_y = bubbles[0][1]
    # Scroll until the topmost visible bubble is in the top quarter of the screen
    return topmost_y > SCREEN_H * 0.25


def find_latest_level_tap(img: Image.Image) -> tuple[int, int] | None:
    """
    Find the latest (highest-numbered) accessible level bubble on the map
    and return its (x, y) tap coordinates.

    Uses pink-filtered real level bubbles.  The topmost bubble (smallest y)
    on the scrolled-to-top map is the latest/newest level.
    Falls back to finding the bubble nearest the character avatar.
    """
    bgr = _pil_to_cv(img)

    # Try to locate the character avatar (stands on current level)
    # Avatar has a blue portrait frame (H≈95-130, S>70, V>70)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(hsv,
                             np.array([95, 70, 70]),
                             np.array([130, 255, 255]))
    contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_contour = None
    best_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if 3000 < area < 30000 and area > best_area:
            best_area = area
            best_contour = c

    bubbles = find_real_level_bubbles(img)

    if best_contour is not None and bubbles:
        M = cv2.moments(best_contour)
        if M["m00"] > 0:
            avatar_x = int(M["m10"] / M["m00"])
            avatar_y = int(M["m01"] / M["m00"])
            closest = min(bubbles,
                          key=lambda b: (b[0] - avatar_x) ** 2 + (b[1] - avatar_y) ** 2)
            return closest[0], closest[1]

    # Fallback: topmost pink bubble (newest level when scrolled to top)
    if bubbles:
        return bubbles[0][0], bubbles[0][1]

    return None
