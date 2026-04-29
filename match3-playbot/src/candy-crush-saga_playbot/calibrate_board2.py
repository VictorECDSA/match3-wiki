"""
Calibrate board geometry by combining:
- Level data (9x9 board, trapezoidal shape from level 11 tileMap)
- Brightness dip scan to find row/column boundaries precisely
Saves annotated image to workspace/candy-crush-saga_playbot/screenshots/.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import adb
import numpy as np
from PIL import Image, ImageDraw

SS_DIR = adb.SCREENSHOT_DIR
DATA = Path("/Users/fenghaoming/Documents/Workspace/AI/mine/match3-wiki/match3-playbot/workspace/candy-crush-saga_apk-analysis/all_levels.jsonl")

# ---- Load level 11 tileMap -------------------------------------------------
with open(DATA) as f:
    for i, line in enumerate(f, 1):
        if i == 11:
            level = json.loads(line)
            break

# tileMap structure: list where index 0 = list of 9 row-lists, each with 9 cell strings
tilemap_rows = level["tileMap"][0]   # list of 9 rows
ROWS = level.get("boardRows", 9)
COLS = level.get("boardColumns", 9)

print(f"Level 11: {ROWS}x{COLS} board")
print("Active cells per row:")
for r, row in enumerate(tilemap_rows):
    active = [c != "000" for c in row]
    print(f"  row {r}: {''.join('#' if a else '.' for a in active)}")

# ---- Load screenshot -------------------------------------------------------
img = Image.open(SS_DIR / "ingame_level11.png")
arr = np.array(img)
gray = arr[:, :, :3].mean(axis=2)

# ---- Find column boundaries via vertical brightness scan ------------------
# Scan center strip of board (y=1400-1700 = rows 4-5, all 9 cols active)
BOARD_X0, BOARD_X1 = 45, 1175
col_strip = gray[1400:1700, BOARD_X0:BOARD_X1]
col_mean = col_strip.mean(axis=0)  # mean per column

# Find local minima (inter-cell gaps) in the column profile
from scipy.signal import find_peaks
# Use negative to find minima
neg_col = -col_mean
peaks, props = find_peaks(neg_col, distance=80, prominence=5)
print(f"\nColumn gap candidates (relative to x={BOARD_X0}): {peaks}")
print(f"  Absolute x: {peaks + BOARD_X0}")

# ---- Find row boundaries via horizontal brightness scan -------------------
row_strip = gray[840:2150, BOARD_X0:BOARD_X1]
row_mean = row_strip.mean(axis=1)  # mean per row

neg_row = -row_mean
row_peaks, _ = find_peaks(neg_row, distance=100, prominence=8)
print(f"\nRow gap candidates (relative to y=840): {row_peaks}")
print(f"  Absolute y: {row_peaks + 840}")

# ---- Estimate grid from dips ----------------------------------------------
row_bounds_abs = sorted([840] + list(row_peaks + 840) + [2150])
print(f"\nAll row boundaries: {row_bounds_abs}")
print(f"  Row heights: {[row_bounds_abs[i+1]-row_bounds_abs[i] for i in range(len(row_bounds_abs)-1)]}")

# ---- Annotate image -------------------------------------------------------
adb.screenshot(save_as="calibrate2_raw.png")  # fresh screenshot for annotation
img2 = Image.open(SS_DIR / "calibrate2_raw.png")
draw = ImageDraw.Draw(img2)

# Draw column gaps
for px in peaks:
    x = int(px + BOARD_X0)
    draw.line([(x, 840), (x, 2150)], fill=(0, 255, 0), width=2)

# Draw row gaps
for py in row_peaks:
    y = int(py + 840)
    draw.line([(BOARD_X0, y), (BOARD_X1, y)], fill=(255, 0, 0), width=2)

# Draw board border
draw.rectangle([BOARD_X0, 840, BOARD_X1, 2150], outline=(255, 255, 0), width=3)

img2.save(SS_DIR / "calibrate2_grid.png")
print("\nAnnotated image saved -> screenshots/calibrate2_grid.png")
