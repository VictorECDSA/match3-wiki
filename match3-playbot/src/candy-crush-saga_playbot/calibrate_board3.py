"""
Precise board coordinate derivation.
Column centers and row centers for all 9x9 cells.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import adb
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SS_DIR = adb.SCREENSHOT_DIR

# From calibrate_board2.py output:
# Column gaps (inter-cell): x = 152, 283, 414, 545, 675, 806, 937, 1068
# Board left edge ≈ 45, right edge ≈ 1175
# So 9 cells span 1175-45 = 1130px → cell_w = 1130/9 ≈ 125.6px

# Row gaps: y = 940, 1080, 1249, 1390, 1533, 1675, 1816, 1959, 2108
# The first gap at 940 is between spawner row and row 0 tiles.
# Rows 0-8 map to y ranges:
#   row 0: 840-940  (the spawner row at top, irregular)
#   row 1: 940-1080  → but visually this is the first tile row
# Actually from screenshot the tiles start at ~y=870
# Let's use the detected gaps as row separators and compute centers:

COL_GAPS = [45, 152, 283, 414, 545, 675, 806, 937, 1068, 1175]
ROW_GAPS = [840, 940, 1080, 1249, 1390, 1533, 1675, 1816, 1959, 2108]

# Cell centers
col_centers = [(COL_GAPS[i] + COL_GAPS[i+1]) // 2 for i in range(9)]
row_centers = [(ROW_GAPS[i] + ROW_GAPS[i+1]) // 2 for i in range(9)]

print("Column centers (x):", col_centers)
print("Row centers    (y):", row_centers)
print("Cell widths:  ", [COL_GAPS[i+1]-COL_GAPS[i] for i in range(9)])
print("Cell heights: ", [ROW_GAPS[i+1]-ROW_GAPS[i] for i in range(9)])

# ---- Annotate with row/col indices ----------------------------------------
img = Image.open(SS_DIR / "ingame_level11.png")
draw = ImageDraw.Draw(img)

for r, cy in enumerate(row_centers):
    for c, cx in enumerate(col_centers):
        draw.ellipse([cx-8, cy-8, cx+8, cy+8], outline=(255,0,255), width=3)
        draw.text((cx-6, cy-8), f"{r},{c}", fill=(255,255,0))

for x in COL_GAPS:
    draw.line([(x, 840), (x, 2108)], fill=(0,255,0), width=1)
for y in ROW_GAPS:
    draw.line([(45, y), (1175, y)], fill=(255,0,0), width=1)

img.save(SS_DIR / "calibrate3_centers.png")
print("\nAnnotated centers saved -> screenshots/calibrate3_centers.png")
