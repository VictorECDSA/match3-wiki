"""
Print level 11 tileMap correctly to verify board shape.
tileMap structure: tileMap[row][col] = segment string
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import adb

DATA = Path("/Users/fenghaoming/Documents/Workspace/AI/mine/match3-wiki/match3-playbot/workspace/candy-crush-saga_apk-analysis/all_levels.jsonl")

with open(DATA) as f:
    for i, line in enumerate(f, 1):
        if i == 11:
            level = json.loads(line)
            break

tilemap = level["tileMap"]   # tileMap[row][col]
rows = level.get("boardRows", 9)
cols = level.get("boardColumns", 9)
print(f"Level 11: {rows}x{cols}, tileMap type={type(tilemap).__name__}, len={len(tilemap)}")
print(f"tileMap[0] type={type(tilemap[0]).__name__}, len={len(tilemap[0])}")

print("\nActive cell map (# = active, . = empty):")
for r in range(rows):
    row = tilemap[r]
    active = [c != "000" for c in row]
    print(f"  row {r}: {''.join('#' if a else '.' for a in active)}  {row}")
