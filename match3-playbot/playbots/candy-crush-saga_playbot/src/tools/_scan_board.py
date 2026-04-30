"""Scan for board bounding box using horizontal non-teal pixel count."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import adb
import numpy as np

img = adb.screenshot(save_as="scan_raw.png")
arr = np.array(img)
h, w = arr.shape[:2]

# Teal background: G and B both high, R low
# Teal: roughly R<160, G>150, B>150, G≈B
def is_teal(row):
    r, g, b = row[:,0].astype(int), row[:,1].astype(int), row[:,2].astype(int)
    return (g > 130) & (b > 130) & (r < 160) & (np.abs(g.astype(int)-b.astype(int)) < 40)

# Dark blue map background: R~49, G~109, B~156
def is_mapbg(row):
    r, g, b = row[:,0].astype(int), row[:,1].astype(int), row[:,2].astype(int)
    return (r < 80) & (g > 80) & (g < 140) & (b > 120) & (b < 200)

print("Non-background pixel count per row (y=800-2000 step 10):")
for y in range(800, 2000, 10):
    row = arr[y, :, :3]
    bg = is_teal(row) | is_mapbg(row)
    count = int((~bg).sum())
    bar = "#" * (count // 20)
    print(f"  y={y:4d}: {count:4d} {bar}")
