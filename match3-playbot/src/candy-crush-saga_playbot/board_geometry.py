"""
Board geometry constants for Candy Crush Saga on device AI9D6PGMW8DEEIJN.
Screen: 1220x2712, density 520.

All coordinates in full-screen pixels (origin top-left).
Row 0 = top of board (spawner area), row 8 = bottom row.
Col 0 = leftmost column, col 8 = rightmost column.

Derived from calibration run on Level 11 (2025-04-29).
These constants apply to all 9x9 levels on this device.
"""

# Column boundary x-positions (left edge of each cell, plus right edge of last)
COL_GAPS = [45, 152, 283, 414, 545, 675, 806, 937, 1068, 1175]

# Row boundary y-positions (top edge of each row, plus bottom edge of last)
ROW_GAPS = [840, 940, 1080, 1249, 1390, 1533, 1675, 1816, 1959, 2108]

# Cell center x-coordinates per column
COL_CENTERS = [98, 217, 348, 479, 610, 740, 871, 1002, 1121]

# Cell center y-coordinates per row
ROW_CENTERS = [890, 1010, 1164, 1319, 1461, 1604, 1745, 1887, 2033]

NUM_ROWS = 9
NUM_COLS = 9


def cell_center(row: int, col: int) -> tuple[int, int]:
    """Return (x, y) screen coordinates of the center of cell (row, col)."""
    return COL_CENTERS[col], ROW_CENTERS[row]


def cell_bounds(row: int, col: int) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) pixel bounds of cell (row, col)."""
    return COL_GAPS[col], ROW_GAPS[row], COL_GAPS[col + 1], ROW_GAPS[row + 1]
