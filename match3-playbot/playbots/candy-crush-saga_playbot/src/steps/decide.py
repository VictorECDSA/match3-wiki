"""
Step 2 — Decide.

Given a GameState and BotContext, produces an Action.

This is the layer that can be replaced by an external agent:
  - The agent reads GameState (JSON) from steps/capture
  - The agent produces Action (JSON) which steps/execute will carry out

Can be run standalone (reads GameState JSON from --state or stdin):
  python -m steps.decide --state '{"screen_state":"playing","board":...}'
  echo '<GameState JSON>' | python -m steps.decide

  Prints the Action as JSON to stdout.
"""

from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import solver
from core import ui_detector as uid
import bot_logger as logger
from models import (
    GameState, BotContext, Action,
    MAP, PRE_PLAY, PLAYING, COMPLETE, FAILED, UNKNOWN,
    ACT_TAP, ACT_SWAP, ACT_WAIT, ACT_LAUNCH, ACT_SCROLL,
)

_SCREEN_H = 2712
_SCREEN_W = 1220
_CONTINUE_FALLBACK = (610, 2200)
_RETRY_FALLBACK    = (610, 1800)
_DISMISS_FALLBACK  = (610, 2000)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def decide(state: GameState, ctx: BotContext) -> Action:
    """
    Decide what action to take given the current GameState and BotContext.

    Modifies ctx in-place (blacklist updates, counters).
    Returns an Action.
    """
    ss = state.screen_state

    # ------------------------------------------------------------------ MAP
    if ss == MAP:
        ctx.consecutive_unk = 0
        img = _load_img(state)
        if img is not None:
            # Check if we need to scroll up to reveal the latest level.
            # Strategy: if no pink bubble is visible in the top 40% of the
            # screen, the latest (highest-numbered) level is above the fold.
            # We scroll up (swipe finger upward) with a large stroke, up to
            # _MAP_MAX_SCROLLS times before giving up and tapping whatever we see.
            _MAP_MAX_SCROLLS = 12
            needs_scroll = uid.needs_map_scroll(img)
            if needs_scroll and ctx.map_scroll_count < _MAP_MAX_SCROLLS:
                ctx.map_scroll_count += 1
                # Swipe upward: finger moves from y=1800 to y=600 (slow, 400ms)
                action = Action(ACT_SCROLL,
                                tap_x=610, tap_y=1800,
                                tap_x2=610, tap_y2=600,
                                reason=f"map: scroll up to find latest level "
                                       f"(scroll #{ctx.map_scroll_count})")
                logger.log_action("decide", action)
                return action

            # Map is scrolled to the right position — reset scroll counter and tap
            ctx.map_scroll_count = 0
            tap_pos = uid.find_latest_level_tap(img)
            if tap_pos:
                action = Action(ACT_TAP, tap_x=tap_pos[0], tap_y=tap_pos[1],
                                reason="map: tap latest level bubble")
                logger.log_action("decide", action)
                return action

        action = Action(ACT_WAIT, reason="map: no level bubble found, waiting")
        logger.log_action("decide", action)
        return action

    # ------------------------------------------------------------- PRE_PLAY
    if ss == PRE_PLAY:
        ctx.consecutive_unk = 0
        ctx.reset_level()
        img = _load_img(state)
        tap_pos = uid.find_play_button(img) if img is not None else None
        if tap_pos:
            action = Action(ACT_TAP, tap_x=tap_pos[0], tap_y=tap_pos[1],
                            reason="pre_play: tap Play! button")
        else:
            action = Action(ACT_TAP, tap_x=610, tap_y=1635,
                            reason="pre_play: Play button not found, using fallback")
        logger.log_action("decide", action)
        return action

    # --------------------------------------------------------------- PLAYING
    if ss == PLAYING:
        ctx.consecutive_unk = 0
        board = state.board
        if board is None:
            action = Action(ACT_WAIT, reason="playing: board is None")
            logger.log_action("decide", action)
            return action

        if ctx.tilemap is None:
            ctx.tilemap = [["001"] * 9 for _ in range(9)]

        # Blacklist check: board unchanged after last swap
        if (ctx.last_move and ctx.prev_board_hash
                and state.board_hash == ctx.prev_board_hash):
            r1b, c1b, r2b, c2b = ctx.last_move
            ctx.blacklisted[ctx.last_move] = (board[r1b][c1b], board[r2b][c2b])
            logger.log("decide",
                       f"blacklisted {ctx.last_move} (board unchanged, "
                       f"total: {len(ctx.blacklisted)})")
            ctx.last_move = None

        # Expire blacklist entries where cells changed colour
        expired = [
            m for m, (col1, col2) in ctx.blacklisted.items()
            if board[m[0]][m[1]] != col1 or board[m[2]][m[3]] != col2
        ]
        for m in expired:
            del ctx.blacklisted[m]
        if expired:
            logger.log("decide",
                       f"expired {len(expired)} blacklist entries, "
                       f"{len(ctx.blacklisted)} remain")

        ctx.prev_board      = board
        ctx.prev_board_hash = state.board_hash

        # Find best move
        move = solver.find_best_move(board, ctx.tilemap, set(ctx.blacklisted))
        if move is None:
            move = solver.find_any_move(board, ctx.tilemap, set(ctx.blacklisted))

        if move is None:
            ctx.wait_count += 1
            logger.log("decide", f"no move found (wait #{ctx.wait_count})")
            if ctx.wait_count >= 3:
                if ctx.blacklisted:
                    ctx.blacklisted.clear()
                    logger.log("decide", "cleared blacklist to escape stuck state")
                ctx.wait_count = 0
            action = Action(ACT_WAIT, reason=f"no move found (wait #{ctx.wait_count})")
            logger.log_action("decide", action)
            return action

        ctx.wait_count = 0
        r1, c1, r2, c2 = move
        ctx.move_count += 1
        ctx.last_move = move
        action = Action(ACT_SWAP, r1=r1, c1=c1, r2=r2, c2=c2,
                        reason=f"move {ctx.move_count}: ({r1},{c1})<->({r2},{c2})")
        logger.log_action("decide", action, move_count=ctx.move_count)
        return action

    # -------------------------------------------------------------- COMPLETE
    if ss == COMPLETE:
        ctx.consecutive_unk = 0
        ctx.current_level = None
        ctx.tilemap       = None
        img = _load_img(state)
        tap_pos = _find_green_button(img) if img is not None else None
        if tap_pos is None:
            tap_pos = _CONTINUE_FALLBACK
        action = Action(ACT_TAP, tap_x=tap_pos[0], tap_y=tap_pos[1],
                        reason="complete: tap Continue/Next button")
        logger.log_action("decide", action)
        return action

    # --------------------------------------------------------------- FAILED
    if ss == FAILED:
        ctx.consecutive_unk = 0
        ctx.reset_level()
        img = _load_img(state)
        tap_pos = _find_orange_button(img) if img is not None else None
        if tap_pos is None:
            tap_pos = _RETRY_FALLBACK
        action = Action(ACT_TAP, tap_x=tap_pos[0], tap_y=tap_pos[1],
                        reason="failed: tap Retry button")
        logger.log_action("decide", action)
        return action

    # --------------------------------------------------------------- UNKNOWN
    ctx.consecutive_unk += 1
    if ctx.consecutive_unk % 5 == 1:
        logger.log("decide", f"unknown screen (#{ctx.consecutive_unk})", level="WARN")

    if ctx.consecutive_unk >= 15:
        ctx.consecutive_unk = 0
        img = _load_img(state)
        if img is not None:
            close_pos = uid.find_close_button(img)
            if close_pos:
                action = Action(ACT_TAP, tap_x=close_pos[0], tap_y=close_pos[1],
                                reason="unknown: dismiss via X button")
                logger.log_action("decide", action)
                return action

        strategy = ctx.dismiss_cycle % 4
        ctx.dismiss_cycle += 1
        if strategy == 0:
            action = Action(ACT_TAP, tap_x=30, tap_y=_SCREEN_H // 2,
                            reason="unknown: dismiss left-edge (game-centre panel)")
        elif strategy == 1:
            action = Action(ACT_TAP,
                            tap_x=_DISMISS_FALLBACK[0], tap_y=_DISMISS_FALLBACK[1],
                            reason="unknown: dismiss centre tap")
        elif strategy == 2:
            action = Action(ACT_LAUNCH,
                            reason="unknown: re-launch game to foreground")
        else:
            action = Action(ACT_TAP, tap_x=_SCREEN_W // 2, tap_y=100,
                            reason="unknown: dismiss top-screen tap")
        logger.log_action("decide", action)
        return action

    action = Action(ACT_WAIT,
                    reason=f"unknown screen (#{ctx.consecutive_unk}), waiting")
    logger.log_action("decide", action)
    return action


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_img(state: GameState):
    """Load PIL image from state.screenshot_path, or None on failure."""
    try:
        from PIL import Image
        if state.screenshot_path and state.screenshot_path.exists():
            return Image.open(state.screenshot_path)
    except Exception:
        pass
    return None


def _find_green_button(img) -> tuple[int, int] | None:
    """Locate the green Continue/Next button by HSV scan."""
    import cv2
    import numpy as np
    from core.ui_detector import _pil_to_cv
    bgr = _pil_to_cv(img)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([55, 80, 80]), np.array([95, 255, 255]))
    lower = mask[_SCREEN_H // 2:, :]
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
            return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]) + _SCREEN_H // 2
    return None


def _find_orange_button(img) -> tuple[int, int] | None:
    """Locate the Retry button (orange or hot-pink) by HSV scan."""
    import cv2
    import numpy as np
    from core.ui_detector import _pil_to_cv
    bgr = _pil_to_cv(img)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask_orange = cv2.inRange(hsv, np.array([10, 120, 120]), np.array([25, 255, 255]))
    mask_pink   = cv2.inRange(hsv, np.array([140, 80, 100]), np.array([175, 255, 255]))
    mask = cv2.bitwise_or(mask_orange, mask_pink)
    lower = mask[_SCREEN_H // 2:, :]
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
            return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]) + _SCREEN_H // 2
    return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Decide next action from GameState JSON")
    parser.add_argument("--state", type=str, help="GameState JSON string")
    args = parser.parse_args()

    raw = args.state if args.state else sys.stdin.read()
    state = GameState.from_dict(json.loads(raw))
    ctx   = BotContext()  # fresh context when run standalone

    action = decide(state, ctx)
    print(action.to_json())


if __name__ == "__main__":
    main()
