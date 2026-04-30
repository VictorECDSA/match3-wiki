"""
Step 1 — Capture and Parse.

Takes a screenshot via ADB, detects the screen state, and (when PLAYING)
parses the board grid.  Returns a GameState.

Can be run standalone:
  python -m steps.capture [--stable] [--no-save]

  Prints the GameState as JSON to stdout.
"""

from __future__ import annotations

import sys
import hashlib
import argparse
import time
from pathlib import Path

# Allow running as a script from the package root
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import adb
from core import board_parser as bp
from core import ui_detector as uid
import bot_logger as logger
from models import GameState, PLAYING


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _board_hash(board: list[list[str]]) -> str:
    flat = ",".join(",".join(row) for row in board)
    return hashlib.md5(flat.encode()).hexdigest()[:12]


def capture_and_parse(save_screenshot: bool = True) -> GameState:
    """
    Take a screenshot, detect screen state, parse board if PLAYING.

    Args:
        save_screenshot: if True, saves PNG to SCREENSHOT_DIR.

    Returns:
        GameState with screen_state, screenshot_path, board, board_hash.
    """
    ts = int(time.time())
    fname = f"bot_{ts}.png" if save_screenshot else None

    img = adb.screenshot(save_as=fname)
    screenshot_path = (adb.SCREENSHOT_DIR / fname) if fname else None

    screen_state = uid.detect_screen(img)

    board = None
    board_hash = None
    if screen_state == PLAYING:
        board = bp.parse_board(img)
        board_hash = _board_hash(board)

    state = GameState(
        screen_state    = screen_state,
        screenshot_path = screenshot_path,
        board           = board,
        board_hash      = board_hash,
    )

    logger.log_state("capture", state, screenshot_saved=fname is not None)
    return state


def wait_for_stable_board(delay: float = 1.5, max_wait: float = 8.0) -> GameState:
    """
    Repeatedly capture until two consecutive PLAYING captures yield the same
    board_hash (board has settled after animations).

    Returns:
        GameState with the stable board, or a non-PLAYING GameState if the
        screen changed away from PLAYING during the wait.
    """
    deadline = time.time() + max_wait
    prev_hash: str | None = None

    while time.time() < deadline:
        state = capture_and_parse(save_screenshot=True)
        if state.screen_state != PLAYING:
            return state
        if state.board_hash == prev_hash:
            logger.log("capture", "board stable", board_hash=state.board_hash)
            return state
        prev_hash = state.board_hash
        time.sleep(min(0.6, delay * 0.4))

    state = capture_and_parse(save_screenshot=True)
    logger.log("capture", "board stable (timeout, returning last)", board_hash=state.board_hash)
    return state


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Capture screenshot and parse game state")
    parser.add_argument("--save",    action="store_true", default=True,
                        help="Save screenshot PNG (default: True)")
    parser.add_argument("--no-save", dest="save", action="store_false")
    parser.add_argument("--stable",  action="store_true",
                        help="Wait for stable board before returning")
    parser.add_argument("--delay",   type=float, default=1.5,
                        help="Poll interval when --stable (default 1.5)")
    args = parser.parse_args()

    if args.stable:
        state = wait_for_stable_board(delay=args.delay)
    else:
        state = capture_and_parse(save_screenshot=args.save)

    print(state.to_json())


if __name__ == "__main__":
    main()
