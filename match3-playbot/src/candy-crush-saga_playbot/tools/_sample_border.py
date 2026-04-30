"""Sample board border pixels to calibrate color detection."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import adb
import numpy as np

img = adb.screenshot(save_as="border_sample.png")
arr = np.array(img)

print("Left edge samples (x=45-55, y=850-1900 step 50):")
for y in range(850, 1900, 50):
    px = arr[y, 45:55, :3].mean(axis=0)
    print(f"  y={y}: RGB={px.astype(int)}")

print("\nOutside board (x=15, y=900-1800 step 100):")
for y in range(900, 1800, 100):
    px = arr[y, 15, :3]
    print(f"  y={y}: RGB={px}")

print("\nInside board center (x=610, y=900-1800 step 50):")
for y in range(900, 1800, 50):
    px = arr[y, 610, :3]
    print(f"  y={y}: RGB={px}")
