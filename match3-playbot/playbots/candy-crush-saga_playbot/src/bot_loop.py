"""
Bot main loop.

Runs the three-step cycle indefinitely:
  1. capture_and_parse  -> GameState
  2. decide             -> Action
  3. execute            -> result

Logs every cycle to workspace/candy-crush-saga_playbot/bot.log.

Usage (via run.sh):
  bash run.sh bot_loop.py [--delay 1.5] [--verbose] [--max-moves 200]
"""

from __future__ import annotations

import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import board_parser as bp
import bot_logger as logger
from models import BotContext, PLAYING, ACT_WAIT
from steps.capture import capture_and_parse, wait_for_stable_board
from steps.decide  import decide
from steps.execute import execute


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_bot(max_moves_per_level: int, delay: float, verbose: bool) -> None:
    logger.log("loop", "bot starting — will auto-navigate to latest level",
               max_moves=max_moves_per_level, delay=delay)

    ctx = BotContext()
    cycle = 0

    while True:
        cycle += 1
        logger.log("loop", f"--- cycle {cycle} ---")

        # ------------------------------------------------------------------
        # Step 1: Capture + Parse
        # ------------------------------------------------------------------
        if ctx.consecutive_unk == 0 and _last_state_was_playing(ctx):
            # Board may still be animating — wait for it to settle
            state = wait_for_stable_board(delay=delay)
        else:
            state = capture_and_parse(save_screenshot=True)

        if verbose and state.board is not None:
            bp.print_board(state.board)
            # Save annotated image
            try:
                from PIL import Image
                if state.screenshot_path and state.screenshot_path.exists():
                    img = Image.open(state.screenshot_path)
                    from core import adb
                    ann = bp.annotate_board(img, state.board)
                    ann.save(adb.SCREENSHOT_DIR / f"annotated_{int(time.time())}.png")
            except Exception as e:
                logger.log("loop", f"annotate failed: {e}", level="WARN")

        # ------------------------------------------------------------------
        # Step 2: Decide
        # ------------------------------------------------------------------
        action = decide(state, ctx)

        # ------------------------------------------------------------------
        # Step 3: Execute
        # ------------------------------------------------------------------
        # Adjust sleep duration for PLAYING swaps vs other actions
        if action.action_type == ACT_WAIT and state.screen_state == PLAYING:
            # Use full delay to avoid busy-polling
            execute(action, post_sleep=False)
            time.sleep(delay)
        else:
            execute(action)

        # Cap per-level move count
        if state.screen_state == PLAYING and ctx.move_count >= max_moves_per_level:
            logger.log("loop",
                       f"reached {max_moves_per_level} moves limit this level, resetting count")
            ctx.move_count = 0


def _last_state_was_playing(ctx: BotContext) -> bool:
    """Heuristic: if we have a prev_board, we were just playing."""
    return ctx.prev_board is not None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Candy Crush Saga auto-play bot")
    parser.add_argument("--max-moves", type=int,   default=200,
                        help="Max swaps per level before resetting counter (default 200)")
    parser.add_argument("--delay",     type=float, default=1.5,
                        help="Seconds between moves / poll interval (default 1.5)")
    parser.add_argument("--verbose",   action="store_true",
                        help="Print board grid and save annotated screenshots each move")
    args = parser.parse_args()

    run_bot(
        max_moves_per_level = args.max_moves,
        delay               = args.delay,
        verbose             = args.verbose,
    )


if __name__ == "__main__":
    main()
