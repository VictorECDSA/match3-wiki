"""
Board state parser for Candy Crush Saga.
Takes a PIL screenshot and returns the 9x9 grid of candy colors.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from PIL import Image, ImageDraw

import board_geometry as geo
import color_classifier as cc


def parse_board(img: Image.Image) -> list[list[str]]:
    """
    Parse the board state from a full-screen PIL screenshot.

    Returns:
        9x9 list of color strings (see color_classifier constants).
        board[row][col], row 0 = top.
    """
    arr = np.array(img)
    board = []
    for r in range(geo.NUM_ROWS):
        row = []
        for c in range(geo.NUM_COLS):
            left, top, right, bottom = geo.cell_bounds(r, c)
            # Add small inset to avoid cell borders
            inset = 8
            cell = arr[top + inset: bottom - inset, left + inset: right - inset]
            color = cc.classify_cell(cell)
            row.append(color)
        board.append(row)
    return board


def print_board(board: list[list[str]]) -> None:
    """Print board as a compact grid."""
    abbrev = {
        cc.RED:    "R",
        cc.PINK:   "P",
        cc.ORANGE: "O",
        cc.YELLOW: "Y",
        cc.GREEN:  "G",
        cc.BLUE:   "B",
        cc.PURPLE: "V",
        cc.WHITE:  "W",
        cc.DARK:   "D",
        cc.EMPTY:  ".",
        cc.UNKNOWN:"?",
    }
    for r, row in enumerate(board):
        print(f"  row {r}: " + " ".join(abbrev.get(c, "?") for c in row))


def annotate_board(img: Image.Image, board: list[list[str]]) -> Image.Image:
    """Draw color labels on each cell of the board image."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    abbrev = {
        cc.RED:    ("R", (255,   0,   0)),
        cc.PINK:   ("P", (255, 100, 200)),
        cc.ORANGE: ("O", (255, 140,   0)),
        cc.YELLOW: ("Y", (255, 255,   0)),
        cc.GREEN:  ("G", (  0, 200,   0)),
        cc.BLUE:   ("B", ( 50,  50, 255)),
        cc.PURPLE: ("V", (180,   0, 255)),
        cc.WHITE:  ("W", (220, 220, 220)),
        cc.DARK:   ("D", ( 80,  80,  80)),
        cc.EMPTY:  (".", (100, 200, 200)),
        cc.UNKNOWN:("?", (255, 255, 255)),
    }
    for r in range(geo.NUM_ROWS):
        for c in range(geo.NUM_COLS):
            cx, cy = geo.cell_center(r, c)
            label, color = abbrev.get(board[r][c], ("?", (255,255,255)))
            # Draw white background circle then label
            draw.ellipse([cx-18, cy-18, cx+18, cy+18], fill=(0,0,0,180) if len(color)==4 else (0,0,0))
            draw.text((cx-6, cy-8), label, fill=color)
    return out
