from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Action:
    """Decision produced by step_decide that step_execute will carry out."""

    action_type: str                              # ACT_TAP / ACT_SWAP / ...

    # ACT_TAP
    tap_x: Optional[int]   = None
    tap_y: Optional[int]   = None

    # ACT_SCROLL (swipe from tap_x/tap_y to tap_x2/tap_y2)
    tap_x2: Optional[int]  = None
    tap_y2: Optional[int]  = None

    # ACT_SWAP
    r1: Optional[int]      = None
    c1: Optional[int]      = None
    r2: Optional[int]      = None
    c2: Optional[int]      = None

    reason: str            = ""                   # human-readable explanation

    def to_dict(self) -> dict:
        d: dict = {"action_type": self.action_type, "reason": self.reason}
        if self.tap_x is not None:
            d["tap_x"] = self.tap_x
            d["tap_y"] = self.tap_y
        if self.tap_x2 is not None:
            d["tap_x2"] = self.tap_x2
            d["tap_y2"] = self.tap_y2
        if self.r1 is not None:
            d.update(r1=self.r1, c1=self.c1, r2=self.r2, c2=self.c2)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Action":
        return cls(
            action_type = d["action_type"],
            tap_x       = d.get("tap_x"),
            tap_y       = d.get("tap_y"),
            tap_x2      = d.get("tap_x2"),
            tap_y2      = d.get("tap_y2"),
            r1          = d.get("r1"),
            c1          = d.get("c1"),
            r2          = d.get("r2"),
            c2          = d.get("c2"),
            reason      = d.get("reason", ""),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))
