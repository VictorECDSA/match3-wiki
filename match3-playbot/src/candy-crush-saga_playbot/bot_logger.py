"""
Structured JSON-line logger for the Candy Crush Saga bot.

Each log entry is a single line of JSON written to:
  workspace/candy-crush-saga_playbot/bot.log

Format:
  {"ts": <unix_float>, "step": "<capture|decide|execute|loop>",
   "level": "<INFO|WARN|ERROR>", "msg": "...", ...extra_fields}

Usage:
  from bot_logger import log
  log("capture", "board parsed", board_hash="abc123", screen_state="playing")
"""

from __future__ import annotations

import json
import time
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Log file location
# ---------------------------------------------------------------------------

_WORKSPACE = (
    Path(__file__).parent.parent.parent
    / "workspace"
    / "candy-crush-saga_playbot"
)
_WORKSPACE.mkdir(parents=True, exist_ok=True)

LOG_FILE = _WORKSPACE / "bot.log"

_log_fh = None  # lazily opened file handle


def _get_fh():
    global _log_fh
    if _log_fh is None or _log_fh.closed:
        _log_fh = open(LOG_FILE, "a", buffering=1, encoding="utf-8")
    return _log_fh


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log(step: str, msg: str, level: str = "INFO", **kwargs) -> None:
    """
    Write one JSON-line log entry.

    Args:
        step:   "capture" | "decide" | "execute" | "loop"
        msg:    human-readable description
        level:  "INFO" | "WARN" | "ERROR"
        **kwargs: any extra structured fields to include
    """
    entry = {
        "ts":    round(time.time(), 3),
        "step":  step,
        "level": level,
        "msg":   msg,
    }
    entry.update(kwargs)
    line = json.dumps(entry, default=str, separators=(",", ":"))
    fh = _get_fh()
    fh.write(line + "\n")
    # Also mirror to stdout
    print(f"[{step}] {msg}", flush=True)


def log_state(step: str, game_state, **kwargs) -> None:
    """Convenience: log a GameState dict."""
    log(step, f"screen_state={game_state.screen_state}", **game_state.to_dict(), **kwargs)


def log_action(step: str, action, **kwargs) -> None:
    """Convenience: log an Action dict."""
    log(step, f"action={action.action_type} reason={action.reason!r}",
        **action.to_dict(), **kwargs)


def close() -> None:
    """Flush and close the log file handle."""
    global _log_fh
    if _log_fh and not _log_fh.closed:
        _log_fh.flush()
        _log_fh.close()
