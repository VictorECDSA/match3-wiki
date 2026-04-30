from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotContext:
    """
    Per-run mutable context carried across loop iterations.
    Passed from the loop into step_decide so decisions can use history.
    """

    current_level: Optional[int]     = None
    tilemap: Optional[list]          = None       # 9x9 tileMap strings

    move_count: int                   = 0
    wait_count: int                   = 0
    consecutive_unk: int              = 0
    dismiss_cycle: int                = 0

    prev_board: Optional[list]        = None
    prev_board_hash: Optional[str]    = None
    last_move: Optional[tuple]        = None      # (r1,c1,r2,c2)

    blacklisted: dict                 = field(default_factory=dict)
    # move -> (color1, color2)

    # Map navigation state
    map_scroll_count: int             = 0         # how many scrolls done this MAP session

    def reset_level(self) -> None:
        """Clear per-level state (called on PRE_PLAY / FAILED)."""
        self.move_count   = 0
        self.wait_count   = 0
        self.blacklisted.clear()
        self.prev_board      = None
        self.prev_board_hash = None
        self.last_move       = None
