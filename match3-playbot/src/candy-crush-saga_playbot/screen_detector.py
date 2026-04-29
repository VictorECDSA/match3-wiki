"""
Screen state detection for Candy Crush Saga bot.
Identifies which UI screen is currently visible.
"""

from PIL import Image
import numpy as np


# ---- color helpers --------------------------------------------------------

def _crop_region(img: Image.Image, x: int, y: int, w: int, h: int) -> np.ndarray:
    return np.array(img.crop((x, y, x + w, y + h)))


def _mean_rgb(region: np.ndarray) -> tuple[int, int, int]:
    m = region.reshape(-1, region.shape[-1]).mean(axis=0)
    return (int(m[0]), int(m[1]), int(m[2]))


# ---- screen detection ------------------------------------------------------

class Screen:
    UNKNOWN = "unknown"
    LEVEL_SELECT = "level_select"   # map view
    PRE_PLAY = "pre_play"           # "Play!" dialog
    PLAYING = "playing"             # active gameplay board
    LEVEL_COMPLETE = "level_complete"
    LEVEL_FAILED = "level_failed"
    LOADING = "loading"


def detect_screen(img: Image.Image) -> str:
    """
    Heuristic screen detection based on pixel colours at known landmark positions.
    Screen resolution: 1220 x 2712.

    Returns a Screen constant string.
    """
    w, h = img.size
    arr = np.array(img)

    # -- Pre-play dialog: pink/white region roughly at (150,230)-(1070,900)
    # Sample the "Play!" button area (bottom-center of dialog)
    play_btn_region = _crop_region(img, 270, 820, 680, 80)
    r, g, b = _mean_rgb(play_btn_region)
    if r > 180 and g < 100 and b < 120:  # hot pink
        return Screen.PRE_PLAY

    # -- Level complete: typically a bright yellow/gold banner at top
    top_region = _crop_region(img, 200, 100, 820, 120)
    r, g, b = _mean_rgb(top_region)
    if r > 200 and g > 160 and b < 80:   # golden yellow
        return Screen.LEVEL_COMPLETE

    # -- Active gameplay: green background at top score bar area
    # The move counter is in the upper portion of the board area (approx y=400)
    board_bg = _crop_region(img, 0, 380, 1220, 60)
    r, g, b = _mean_rgb(board_bg)
    if g > 120 and r < 150:               # greenish
        return Screen.PLAYING

    # -- Map/level select: dark blue/purple sky background
    sky = _crop_region(img, 400, 50, 400, 200)
    r, g, b = _mean_rgb(sky)
    if b > r and b > g and b > 80:        # blue-ish
        return Screen.LEVEL_SELECT

    return Screen.UNKNOWN
