"""Read level 11 data from all_levels.jsonl to get ground-truth board shape."""
import json
from pathlib import Path

DATA = Path("/Users/fenghaoming/Documents/Workspace/AI/mine/match3-wiki/match3-playbot/workspace/candy-crush-saga_apk-analysis/all_levels.jsonl")

with open(DATA) as f:
    for i, line in enumerate(f, 1):
        if i == 11:
            level = json.loads(line)
            break

print("id_meta:", level["id_meta"])
print("gameModeName:", level["gameModeName"])
print("moveLimit:", level["moveLimit"])
print("numberOfColours:", level["numberOfColours"])
print("boardRows:", level.get("boardRows", 9))
print("boardColumns:", level.get("boardColumns", 9))
print("_itemsToOrder:", level.get("_itemsToOrder"))
print()

tilemap = level["tileMap"]
print("tileMap (row by row, top=row0):")
rows = level.get("boardRows", 9)
cols = level.get("boardColumns", 9)
# tileMap is a flat list of segment-ID strings, left-to-right, top-to-bottom
# each cell can have multiple segments stacked, separated by some encoding
# Let's just print the raw values
if isinstance(tilemap, list):
    print(f"  type: list, len={len(tilemap)}")
    for r in range(rows):
        row_cells = tilemap[r*cols:(r+1)*cols]
        print(f"  row {r}: {row_cells}")
elif isinstance(tilemap, str):
    print("  type: str")
    print("  raw:", tilemap[:200])
else:
    print("  type:", type(tilemap))
    print("  value:", str(tilemap)[:200])
