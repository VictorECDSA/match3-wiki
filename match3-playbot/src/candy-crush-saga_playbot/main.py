"""
Candy Crush Saga auto-play bot.

Flow:
  1. Capture screenshot
  2. Detect screen state via ui_detector (OpenCV template matching)
  3. Handle state:
       MAP       -> find latest level bubble, tap it
       PRE_PLAY  -> tap Play! button
       PLAYING   -> parse board (JSON), solve, execute best swap
       COMPLETE  -> tap continue / next-level button
       FAILED    -> tap retry button
       UNKNOWN   -> wait and retry
  4. Repeat indefinitely

Usage (via run.sh):
  bash run.sh main.py [--delay 1.5] [--verbose]
"""

import sys
import time
import json
import hashlib
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import adb
import board_parser as bp
import solver
import ui_detector as uid
from ui_detector import (
    MAP, PRE_PLAY, PLAYING, COMPLETE, FAILED, UNKNOWN,
    find_play_button, find_close_button, find_latest_level_tap,
)

# ---------------------------------------------------------------------------
# Continue / Retry button scan (template-independent fallback)
# ---------------------------------------------------------------------------

def _find_green_button(img) -> tuple[int, int] | None:
    """Find a large green button (Continue / Next) by HSV colour scan."""
    import cv2
    import numpy as np
    bgr = uid._pil_to_cv(img)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([55, 80, 80]), np.array([95, 255, 255]))
    # Find largest green blob in lower half
    lower = mask[SCREEN_H // 2 :, :]
    contours, _ = cv2.findContours(lower, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_area = None, 0
    for c in contours:
        area = cv2.contourArea(c)
        if area > best_area:
            best_area = area
            best = c
    if best is not None and best_area > 5000:
        M = cv2.moments(best)
        if M["m00"] > 0:
            return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]) + SCREEN_H // 2
    return None


def _find_orange_button(img) -> tuple[int, int] | None:
    """Find a large orange button (Retry) by HSV colour scan."""
    import cv2
    import numpy as np
    bgr = uid._pil_to_cv(img)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([10, 120, 120]), np.array([25, 255, 255]))
    lower = mask[SCREEN_H // 2 :, :]
    contours, _ = cv2.findContours(lower, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_area = None, 0
    for c in contours:
        area = cv2.contourArea(c)
        if area > best_area:
            best_area = area
            best = c
    if best is not None and best_area > 5000:
        M = cv2.moments(best)
        if M["m00"] > 0:
            return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]) + SCREEN_H // 2
    return None


SCREEN_W = adb.SCREEN_W
SCREEN_H = adb.SCREEN_H

# Fallback fixed tap positions (used only when colour scan also fails)
_CONTINUE_FALLBACK = (610, 2200)
_RETRY_FALLBACK    = (610, 1800)
_DISMISS_FALLBACK  = (610, 2000)


# ---------------------------------------------------------------------------
# Board helpers
# ---------------------------------------------------------------------------

def _board_hash(board: list[list[str]]) -> str:
    flat = ",".join(",".join(row) for row in board)
    return hashlib.md5(flat.encode()).hexdigest()[:12]


def _board_to_json(board: list[list[str]]) -> str:
    """Return compact JSON representation of the board for logging."""
    return json.dumps(board, separators=(",", ":"))


def _wait_for_stable_board(delay: float, max_wait: float = 8.0):
    """
    Poll until two consecutive board parses produce the same hash.
    Returns (img, board) or (img, None) if the screen changed away from PLAYING.
    """
    deadline = time.time() + max_wait
    prev_hash: str | None = None

    while time.time() < deadline:
        ts = int(time.time())
        img = adb.screenshot(save_as=f"bot_{ts}.png")
        state = uid.detect_screen(img)
        if state != PLAYING:
            return img, None
        board = bp.parse_board(img)
        h = _board_hash(board)
        if h == prev_hash:
            return img, board
        prev_hash = h
        time.sleep(min(0.6, delay * 0.4))

    img = adb.screenshot(save_as=f"bot_{int(time.time())}.png")
    return img, bp.parse_board(img)


# ---------------------------------------------------------------------------
# Swap execution
# ---------------------------------------------------------------------------

def execute_swap(r1: int, c1: int, r2: int, c2: int):
    import board_geometry as geo
    x1, y1 = geo.cell_center(r1, c1)
    x2, y2 = geo.cell_center(r2, c2)
    print(f"  swipe ({r1},{c1})->({r2},{c2})  px ({x1},{y1})->({x2},{y2})")
    adb.swipe(x1, y1, x2, y2, duration_ms=180)


# ---------------------------------------------------------------------------
# Level data (needed by solver for tileMap)
# ---------------------------------------------------------------------------

_DATA_FILE = (
    Path(__file__).parent.parent.parent
    / "workspace"
    / "candy-crush-saga_apk-analysis"
    / "all_levels.jsonl"
)

_level_cache: dict[int, dict] = {}


def _load_level(level_num: int) -> dict | None:
    if level_num in _level_cache:
        return _level_cache[level_num]
    try:
        with open(_DATA_FILE) as f:
            for i, line in enumerate(f, 1):
                if i == level_num:
                    data = json.loads(line)
                    _level_cache[level_num] = data
                    return data
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main bot loop
# ---------------------------------------------------------------------------

def run_bot(max_moves_per_level: int, delay: float, verbose: bool):
    print("[bot] starting — will auto-navigate to latest level")

    current_level: int | None = None
    tilemap: list[list[str]] | None = None

    move_count        = 0
    wait_count        = 0
    last_state        = None
    consecutive_unk   = 0
    dismiss_cycle     = 0   # increments each time we actually attempt a dismiss
    prev_board        = None
    last_move         = None
    blacklisted: dict = {}  # move -> (color1, color2)

    while True:
        # --- screenshot ------------------------------------------------------
        ts  = int(time.time())
        img = adb.screenshot(save_as=f"bot_{ts}.png")
        state = uid.detect_screen(img)

        if state != last_state:
            print(f"[bot] state: {state}")
            last_state  = state
            wait_count  = 0

        # ====================================================================
        if state == MAP:
            consecutive_unk = 0
            tap_pos = find_latest_level_tap(img)
            if tap_pos:
                print(f"[bot] map: tapping latest level bubble at {tap_pos}")
                adb.tap(*tap_pos)
            else:
                print("[bot] map: could not find level bubble, waiting ...")
            time.sleep(2.5)

        # ====================================================================
        elif state == PRE_PLAY:
            consecutive_unk = 0
            play_pos = find_play_button(img)
            if play_pos:
                print(f"[bot] pre-play: tapping Play! at {play_pos}")
                adb.tap(*play_pos)
            else:
                print("[bot] pre-play: Play button not found, using fallback")
                adb.tap(610, 1635)
            # Reset per-level state
            move_count = 0
            blacklisted.clear()
            prev_board = None
            last_move  = None
            time.sleep(2.5)

        # ====================================================================
        elif state == PLAYING:
            consecutive_unk = 0

            # Wait for board to settle
            img, board = _wait_for_stable_board(delay)
            if board is None:
                continue  # screen changed mid-wait

            if verbose:
                bp.print_board(board)
            print(f"[bot] board JSON: {_board_to_json(board)}")

            # Save annotated debug image
            ann = bp.annotate_board(img, board)
            ann.save(adb.SCREENSHOT_DIR / f"annotated_{ts}.png")

            # Detect which level we're on (needed for tileMap)
            if current_level is None or tilemap is None:
                # Try to infer level number from the move counter UI or use a
                # default; for now we re-use the last known level or default 11
                print("[bot] warning: level number unknown, solver will run without tileMap constraints")
                tilemap = [["001"] * 9 for _ in range(9)]  # all-active dummy

            # Blacklist check: if board unchanged after last swap, blacklist it
            if last_move and prev_board and _board_hash(board) == _board_hash(prev_board):
                r1b, c1b, r2b, c2b = last_move
                blacklisted[last_move] = (board[r1b][c1b], board[r2b][c2b])
                print(f"[bot] blacklisted {last_move} (board unchanged, total: {len(blacklisted)})")
                last_move = None

            # Expire blacklist entries where cells changed colour
            expired = [
                m for m, (col1, col2) in blacklisted.items()
                if board[m[0]][m[1]] != col1 or board[m[2]][m[3]] != col2
            ]
            for m in expired:
                del blacklisted[m]
            if expired:
                print(f"[bot] expired {len(expired)} blacklist entries, {len(blacklisted)} remain")

            prev_board = board

            # Find best move
            move = solver.find_best_move(board, tilemap, set(blacklisted))
            if move is None:
                move = solver.find_any_move(board, tilemap, set(blacklisted))

            if move is None:
                wait_count += 1
                print(f"[bot] no move found (wait #{wait_count})")
                if wait_count >= 3:
                    if blacklisted:
                        print("[bot] clearing blacklist to escape stuck state")
                        blacklisted.clear()
                    else:
                        time.sleep(1.5)
                    wait_count = 0
                time.sleep(delay)
                continue

            wait_count = 0
            r1, c1, r2, c2 = move
            print(f"[bot] move {move_count + 1}: ({r1},{c1})<->({r2},{c2})")
            last_move = move
            execute_swap(r1, c1, r2, c2)
            move_count += 1

            if move_count >= max_moves_per_level:
                print(f"[bot] reached {max_moves_per_level} moves limit for this level")
                move_count = 0

            time.sleep(1.0)

        # ====================================================================
        elif state == COMPLETE:
            consecutive_unk = 0
            print("[bot] level complete!")
            current_level = None  # will re-detect on map
            tilemap = None
            # Tap green Continue/Next button
            pos = _find_green_button(img) or _CONTINUE_FALLBACK
            print(f"[bot] tapping Continue at {pos}")
            adb.tap(*pos)
            time.sleep(3.5)

        # ====================================================================
        elif state == FAILED:
            consecutive_unk = 0
            print(f"[bot] level failed after {move_count} moves — retrying")
            move_count = 0
            blacklisted.clear()
            prev_board = None
            last_move  = None
            pos = _find_orange_button(img) or _RETRY_FALLBACK
            print(f"[bot] tapping Retry at {pos}")
            adb.tap(*pos)
            time.sleep(3.5)

        # ====================================================================
        else:
            consecutive_unk += 1
            if consecutive_unk % 5 == 1:
                print(f"[bot] unknown screen (#{consecutive_unk}), waiting ...")
            # After 15 consecutive unknowns attempt a dismiss
            if consecutive_unk >= 15:
                close_pos = find_close_button(img)
                if close_pos:
                    print(f"[bot] dismissing popup via X at {close_pos}")
                    adb.tap(*close_pos)
                else:
                    # Rotate through strategies each time we hit the threshold.
                    # dismiss_cycle is NOT reset to 0 so each trigger picks the
                    # next strategy in sequence:
                    #   0: BACK key  (clears most system overlays)
                    #   1: tap left edge (collapse side-panel / game-centre)
                    #   2: centre tap (generic dismiss)
                    #   3: tap top of screen
                    strategy = dismiss_cycle % 4
                    if strategy == 0:
                        print("[bot] dismiss: BACK key")
                        adb.keyevent("KEYCODE_BACK")
                    elif strategy == 1:
                        print("[bot] dismiss: left-edge tap (game-centre panel)")
                        adb.tap(30, SCREEN_H // 2)
                    elif strategy == 2:
                        print("[bot] dismiss: centre tap")
                        adb.tap(*_DISMISS_FALLBACK)
                    else:
                        print("[bot] dismiss: top-screen tap")
                        adb.tap(SCREEN_W // 2, 100)
                    dismiss_cycle += 1
                consecutive_unk = 0
            time.sleep(1.5)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Candy Crush Saga auto-play bot")
    parser.add_argument("--max-moves", type=int,   default=200,
                        help="Max swaps per level before giving up (default 200)")
    parser.add_argument("--delay",     type=float, default=1.5,
                        help="Seconds between moves (default 1.5)")
    parser.add_argument("--verbose",   action="store_true",
                        help="Print board grid each move")
    args = parser.parse_args()

    run_bot(
        max_moves_per_level=args.max_moves,
        delay=args.delay,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
