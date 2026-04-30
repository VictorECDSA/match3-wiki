"""
Step 3 — Execute.

Given an Action, carries it out via ADB (tap, swipe, launch).

Can be run standalone:
  python -m steps.execute --action '{"action_type":"tap","tap_x":610,"tap_y":1635}'
  python -m steps.execute --action '{"action_type":"swap","r1":0,"c1":3,"r2":0,"c2":4}'
  python -m steps.execute --action '{"action_type":"launch"}'
  echo '<Action JSON>' | python -m steps.execute

  Prints execution result as JSON to stdout.
"""

from __future__ import annotations

import sys
import json
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import adb
from core import board_geometry as geo
import bot_logger as logger
from models import Action, ACT_TAP, ACT_SWAP, ACT_WAIT, ACT_LAUNCH


_SLEEP_AFTER: dict[str, float] = {
    ACT_TAP:    2.5,
    ACT_SWAP:   1.0,
    ACT_WAIT:   1.5,
    ACT_LAUNCH: 3.0,
}


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def execute(action: Action, post_sleep: bool = True) -> dict:
    """
    Execute the given Action via ADB.

    Args:
        action:     Action to execute.
        post_sleep: if True, sleep after execution to allow animation to finish.

    Returns:
        Result dict with keys: action_type, ok, detail.
    """
    at = action.action_type

    if at == ACT_WAIT:
        logger.log("execute", f"wait — {action.reason}")
        if post_sleep:
            time.sleep(_SLEEP_AFTER[ACT_WAIT])
        return {"action_type": at, "ok": True, "detail": "waited"}

    if at == ACT_TAP:
        x, y = action.tap_x, action.tap_y
        logger.log("execute", f"tap ({x},{y}) — {action.reason}")
        adb.tap(x, y)
        if post_sleep:
            time.sleep(_SLEEP_AFTER[ACT_TAP])
        return {"action_type": at, "ok": True, "detail": f"tapped ({x},{y})"}

    if at == ACT_SWAP:
        r1, c1, r2, c2 = action.r1, action.c1, action.r2, action.c2
        x1, y1 = geo.cell_center(r1, c1)
        x2, y2 = geo.cell_center(r2, c2)
        logger.log("execute",
                   f"swap ({r1},{c1})->({r2},{c2}) "
                   f"px ({x1},{y1})->({x2},{y2}) — {action.reason}")
        adb.swipe(x1, y1, x2, y2, duration_ms=180)
        if post_sleep:
            time.sleep(_SLEEP_AFTER[ACT_SWAP])
        return {
            "action_type": at,
            "ok": True,
            "detail": f"swiped ({x1},{y1})->({x2},{y2})",
        }

    if at == ACT_LAUNCH:
        logger.log("execute", f"launch game — {action.reason}")
        adb.launch_game()
        if post_sleep:
            time.sleep(_SLEEP_AFTER[ACT_LAUNCH])
        return {"action_type": at, "ok": True, "detail": "launched game"}

    logger.log("execute", f"unknown action_type={at!r}", level="WARN")
    return {"action_type": at, "ok": False, "detail": f"unknown action_type: {at}"}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Execute an Action via ADB")
    parser.add_argument("--action",   type=str, help="Action JSON string")
    parser.add_argument("--no-sleep", dest="sleep", action="store_false", default=True,
                        help="Skip post-execution sleep")
    args = parser.parse_args()

    raw = args.action if args.action else sys.stdin.read()
    action = Action.from_dict(json.loads(raw))
    result = execute(action, post_sleep=args.sleep)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
