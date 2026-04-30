"""
Candy Crush Saga auto-play bot — CLI entry point.

Delegates all logic to bot_loop.run_bot().

Three-step cycle (each independently triggerable):
  1. step_capture.py  — screenshot + screen-state detection + board parse
  2. step_decide.py   — decide next action (replaceable by an agent)
  3. step_execute.py  — carry out the action via ADB

Usage (via run.sh):
  bash run.sh main.py [--delay 1.5] [--verbose] [--max-moves 200]

Run individual steps:
  python step_capture.py [--stable]
  python step_decide.py  --state '<GameState JSON>'
  python step_execute.py --action '<Action JSON>'

Log file:
  workspace/candy-crush-saga_playbot/bot.log   (JSON-line format)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bot_loop import main

if __name__ == "__main__":
    main()
