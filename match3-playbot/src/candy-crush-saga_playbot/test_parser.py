"""
Test board parser on the level 11 in-game screenshot.
Run via: bash run.sh test_parser.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import adb
from PIL import Image
import board_parser as bp

SS_DIR = adb.SCREENSHOT_DIR

img = Image.open(SS_DIR / "ingame_level11.png")
board = bp.parse_board(img)

print("Parsed board:")
bp.print_board(board)

out = bp.annotate_board(img, board)
out.save(SS_DIR / "parsed_level11.png")
print("\nAnnotated image saved -> screenshots/parsed_level11.png")
