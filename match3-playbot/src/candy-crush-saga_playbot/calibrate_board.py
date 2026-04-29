"""
Board geometry calibration for Level 11 (and similar levels).
Finds the pixel bounding box and cell size of the game board.
Saves annotated debug images to workspace/candy-crush-saga_playbot/screenshots/.

Run via:  bash run.sh calibrate_board.py
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

# Make sibling imports work when run directly
sys.path.insert(0, str(Path(__file__).parent))
import adb

WORKSPACE = adb.WORKSPACE
SS_DIR = adb.SCREENSHOT_DIR


def find_board_bounds(arr: np.ndarray) -> tuple[int, int, int, int]:
    """
    Detect the board bounding box by finding the teal/cyan background
    colour transition into the darker board-tile area.

    Returns (left, top, right, bottom) in full-image pixels.
    """
    h, w = arr.shape[:2]

    # The board cells are mostly NOT teal.
    # Teal background: G > R, G > B, G > 140
    teal = (arr[:, :, 1].astype(int) - arr[:, :, 0].astype(int) > 30) & \
           (arr[:, :, 1] > 140)
    non_teal = ~teal

    # Find bounding box of non-teal pixels (the board + HUD)
    rows = np.any(non_teal, axis=1)
    cols = np.any(non_teal, axis=0)
    top_all = int(np.argmax(rows))
    bottom_all = h - int(np.argmax(rows[::-1])) - 1
    left_all = int(np.argmax(cols))
    right_all = w - int(np.argmax(cols[::-1])) - 1

    # The HUD (score bar) is at the very top.  The board starts below it.
    # Look for the first row below y=200 that has a wide non-teal span
    board_top = top_all
    for y in range(200, h):
        row_nt = non_teal[y, :]
        span = int(np.sum(row_nt))
        if span > w * 0.3:
            # keep scanning until we find a row where the span is wider
            # than a certain threshold — that's where the top row of tiles is
            if span > w * 0.25:
                board_top = y
                break

    return left_all, board_top, right_all, bottom_all


def estimate_cell_size(arr: np.ndarray, board_left: int, board_top: int,
                       board_right: int, board_bottom: int) -> float:
    """Estimate cell size in pixels from vertical candy boundary detection."""
    board_h = board_bottom - board_top
    board_w = board_right - board_left

    # Typical CCS board is 9 rows; but Level 11 tileMap shows a trapezoidal
    # shape — we'll estimate from the widest row count visible (~9 cols wide)
    # Use the bottom-most full-width row band to measure
    bottom_band = arr[board_bottom - 20: board_bottom, board_left: board_right]

    # Try cell widths from 80 to 160 px and pick best fit
    best_w = board_w / 9  # fallback
    return best_w


def annotate(img: Image.Image, grid_left: int, grid_top: int,
             cell_px: float, rows: int, cols_per_row: list[int]) -> Image.Image:
    """Draw grid overlay on image for visual inspection."""
    out = img.copy().convert("RGBA")
    draw = ImageDraw.Draw(out)
    for r in range(rows + 1):
        y = int(grid_top + r * cell_px)
        draw.line([(grid_left, y), (grid_left + int(cell_px * 9), y)],
                  fill=(255, 0, 0, 180), width=2)
    for c in range(10):
        x = int(grid_left + c * cell_px)
        draw.line([(x, grid_top), (x, int(grid_top + rows * cell_px))],
                  fill=(0, 255, 0, 180), width=2)
    return out.convert("RGB")


def main():
    print("[calibrate] Taking screenshot...")
    img = adb.screenshot(save_as="calibrate_raw.png")
    arr = np.array(img)
    h, w = arr.shape[:2]
    print(f"[calibrate] Screen size: {w}x{h}")

    # ---- Locate the board ------------------------------------------------
    # From visual inspection of level 11:
    # Board area runs roughly y=840-1900, x=50-1170
    # The board is inside a dark blue rounded rectangle border.
    # Detect by finding the blue-grey border colour.

    # Blue board border colour is approximately (60-90, 90-130, 140-180)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    border_mask = (r > 40) & (r < 110) & \
                  (g > 80) & (g < 160) & \
                  (b > 120) & (b < 200) & \
                  (b > r + 30) & (b > g - 20)

    border_ys = np.where(np.any(border_mask, axis=1))[0]
    border_xs = np.where(np.any(border_mask, axis=0))[0]

    if len(border_ys) > 10 and len(border_xs) > 10:
        board_top = int(border_ys.min())
        board_bottom = int(border_ys.max())
        board_left = int(border_xs.min())
        board_right = int(border_xs.max())
        print(f"[calibrate] Border-detected board: "
              f"x={board_left}-{board_right}, y={board_top}-{board_bottom}")
    else:
        # Fallback from visual inspection
        board_top, board_bottom, board_left, board_right = 840, 1900, 45, 1175
        print(f"[calibrate] Fallback board bounds: "
              f"x={board_left}-{board_right}, y={board_top}-{board_bottom}")

    board_w = board_right - board_left
    board_h = board_bottom - board_top

    # Level 11 tileMap: 9 cols, 9 rows.  Trapezoidal (top rows narrower).
    # Measure cell size from bottom full-width rows.
    num_cols = 9
    cell_px = board_w / num_cols
    num_rows = round(board_h / cell_px)
    print(f"[calibrate] board_w={board_w}, board_h={board_h}")
    print(f"[calibrate] cell_px={cell_px:.1f}, inferred rows={num_rows}")

    # ---- Save annotated image -------------------------------------------
    out = img.copy()
    draw = ImageDraw.Draw(out)

    # Draw board bounding box
    draw.rectangle([board_left, board_top, board_right, board_bottom],
                   outline=(255, 255, 0), width=4)

    # Draw grid lines
    for r in range(num_rows + 1):
        y = int(board_top + r * cell_px)
        draw.line([(board_left, y), (board_right, y)], fill=(255, 0, 0), width=2)
    for c in range(num_cols + 1):
        x = int(board_left + c * cell_px)
        draw.line([(x, board_top), (x, board_bottom)], fill=(0, 255, 0), width=2)

    # Mark cell centers
    for r in range(num_rows):
        for c in range(num_cols):
            cx = int(board_left + (c + 0.5) * cell_px)
            cy = int(board_top + (r + 0.5) * cell_px)
            draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 0, 255))

    out.save(SS_DIR / "calibrate_grid.png")
    print(f"[calibrate] Annotated grid saved -> screenshots/calibrate_grid.png")

    # ---- Print summary for board_parser constants ----------------------
    print("\n[calibrate] === BOARD CONSTANTS ===")
    print(f"BOARD_LEFT   = {board_left}")
    print(f"BOARD_TOP    = {board_top}")
    print(f"BOARD_RIGHT  = {board_right}")
    print(f"BOARD_BOTTOM = {board_bottom}")
    print(f"CELL_PX      = {cell_px:.1f}")
    print(f"NUM_ROWS     = {num_rows}")
    print(f"NUM_COLS     = {num_cols}")


if __name__ == "__main__":
    main()
