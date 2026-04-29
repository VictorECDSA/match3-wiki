"""Find grid row/column boundaries by scanning for periodic low-brightness gaps."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import adb
import numpy as np
from PIL import Image

SS_DIR = adb.SCREENSHOT_DIR
img = Image.open(SS_DIR / "ingame_level11.png")
arr = np.array(img)

# Convert to grayscale
gray = arr[:,:,:3].mean(axis=2)

# Scan vertical profile (mean brightness per row) in board X range
board_x0, board_x1 = 100, 1120
strip = gray[:, board_x0:board_x1]
row_mean = strip.mean(axis=1)

print("Row mean brightness (y=840-1920 step 5):")
for y in range(840, 1920, 5):
    val = row_mean[y]
    bar = "#" * int(val // 5)
    print(f"  y={y:4d}: {val:6.1f}  {bar}")
