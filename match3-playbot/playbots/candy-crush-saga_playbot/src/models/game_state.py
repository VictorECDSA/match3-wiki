from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GameState:
    """Snapshot of one bot loop cycle's parsed screen."""

    screen_state: str                           # MAP / PRE_PLAY / PLAYING / ...
    screenshot_path: Optional[Path]   = None    # saved PNG path
    board: Optional[list[list[str]]]  = None    # 9x9 grid (only when PLAYING)
    board_hash: Optional[str]         = None    # MD5[:12] of board

    def to_dict(self) -> dict:
        return {
            "screen_state":    self.screen_state,
            "screenshot_path": str(self.screenshot_path) if self.screenshot_path else None,
            "board":           self.board,
            "board_hash":      self.board_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        sp = d.get("screenshot_path")
        return cls(
            screen_state    = d["screen_state"],
            screenshot_path = Path(sp) if sp else None,
            board           = d.get("board"),
            board_hash      = d.get("board_hash"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))
