"""
Candy color classifier for Candy Crush Saga board parser.

Identifies the dominant candy color in a cell crop using HSV clustering.
Level 11 uses 4 colors (numberOfColours=4).

Color palette (approximate HSV hue ranges, degrees 0-360):
  RED   : hue 340-360 or 0-15,  high saturation
  PINK  : hue 320-345,          medium saturation
  ORANGE: hue 20-40
  YELLOW: hue 45-65
  GREEN : hue 100-150
  BLUE  : hue 195-230
  PURPLE: hue 260-300

OBSTACLE / BLOCKER cells (not a candy color):
  SWIRL (liquorice swirl): dark brownish-black center
  ICING (white): near-white, low saturation
  EMPTY: near-teal background
"""

import numpy as np
from PIL import Image

# Color label constants
RED    = "red"
PINK   = "pink"
ORANGE = "orange"
YELLOW = "yellow"
GREEN  = "green"
BLUE   = "blue"
PURPLE = "purple"
WHITE  = "white"    # icing / marshmallow-swirl obstacle
DARK   = "dark"     # liquorice swirl center
EMPTY  = "empty"    # teal background (no candy)
UNKNOWN = "unknown"


def rgb_to_hsv(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert R,G,B in [0,255] to H [0,360], S [0,1], V [0,1]."""
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
    cmax = max(r_, g_, b_)
    cmin = min(r_, g_, b_)
    delta = cmax - cmin

    if delta == 0:
        h = 0.0
    elif cmax == r_:
        h = 60 * (((g_ - b_) / delta) % 6)
    elif cmax == g_:
        h = 60 * (((b_ - r_) / delta) + 2)
    else:
        h = 60 * (((r_ - g_) / delta) + 4)

    s = 0.0 if cmax == 0 else delta / cmax
    v = cmax
    return h, s, v


def dominant_color_hsv(crop: np.ndarray) -> tuple[float, float, float]:
    """
    Compute the dominant non-background HSV from a cell crop.
    Ignores near-teal pixels (board background).
    Returns (hue, saturation, value) of the dominant colour.
    """
    h, w = crop.shape[:2]
    pixels = crop[:, :, :3].reshape(-1, 3).astype(float)

    # Filter out teal background: G≈B, both >120, R<160
    r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    teal_mask = (g > 110) & (b > 110) & (r < 160) & (np.abs(g - b) < 40)
    fg = pixels[~teal_mask]

    if len(fg) < 10:
        return (180.0, 0.8, 0.5)  # default teal — empty cell

    # Also filter near-white (icing/marshmallow background of obstacle)
    # We want the most saturated pixels
    hsv_all = np.array([rgb_to_hsv(p[0], p[1], p[2]) for p in fg])
    sat = hsv_all[:, 1]

    # Use top-25% most saturated pixels as "candy color signal"
    thresh = np.percentile(sat, 75)
    vivid = hsv_all[sat >= thresh]

    if len(vivid) == 0:
        vivid = hsv_all

    mean_h = float(vivid[:, 0].mean())
    mean_s = float(vivid[:, 1].mean())
    mean_v = float(vivid[:, 2].mean())
    return mean_h, mean_s, mean_v


def classify_cell(crop: np.ndarray) -> str:
    """
    Classify the candy / obstacle type in a cell crop.

    Args:
        crop: numpy array (H, W, 3 or 4) of the cell pixels.

    Returns:
        One of the color constants defined above.
    """
    h, s, v = dominant_color_hsv(crop)

    # Low value → dark (liquorice swirl)
    if v < 0.25:
        return DARK

    # Low saturation → white/grey (icing, marshmallow obstacle, or empty)
    if s < 0.15:
        if v > 0.85:
            return WHITE
        # Check if background teal
        pixels = crop[:, :, :3].astype(float).mean(axis=(0, 1))
        r, g, b = pixels
        if g > 120 and b > 120 and r < 160 and abs(float(g) - float(b)) < 40:
            return EMPTY
        return WHITE

    # Classify by hue
    if h < 15 or h >= 345:
        return RED
    if 15 <= h < 40:
        return ORANGE
    if 40 <= h < 75:
        return YELLOW
    if 75 <= h < 165:
        return GREEN
    if 165 <= h < 255:
        return BLUE
    if 255 <= h < 310:
        return PURPLE
    if 310 <= h < 345:
        return PINK

    return UNKNOWN
