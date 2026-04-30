"""
Match-3 solver for Candy Crush Saga.
Given a board state and the level's tileMap, finds all valid swaps
that create matches of 3+ candies and scores them.
"""

from . import color_classifier as cc

# Colors that are "empty" or unmovable (obstacles / background)
_UNMOVABLE = {cc.EMPTY, cc.WHITE, cc.DARK, cc.UNKNOWN}

# Segment codes for cells whose candy CANNOT be directly swapped.
# 159 = marmalade (encased candy, freed only by adjacent matches)
# 160 = double-layer marmalade / locked candy
_LOCKED_SEGMENTS = {"159", "160"}


def _active_mask(tilemap_rows: list[list[str]]) -> list[list[bool]]:
    """
    Return 9x9 bool grid: True if cell is active (not '000').
    tilemap_rows[r][c] is the segment string for row r, col c.
    """
    return [[cell != "000" for cell in row] for row in tilemap_rows]


def _swappable_mask(tilemap_rows: list[list[str]]) -> list[list[bool]]:
    """
    Return 9x9 bool grid: True if the candy in this cell can be directly swapped.
    Locked cells (marmalade 159/160) are NOT swappable even though they are active.
    """
    result = []
    for row in tilemap_rows:
        r_mask = []
        for cell in row:
            if cell == "000":
                r_mask.append(False)
            elif any(code in cell.split() or code in _split_segments(cell)
                     for code in _LOCKED_SEGMENTS):
                r_mask.append(False)
            else:
                r_mask.append(True)
        result.append(r_mask)
    return result


def _split_segments(cell: str) -> list[str]:
    """Split a segment string like '001159' into 3-char codes: ['001', '159']."""
    return [cell[i:i+3] for i in range(0, len(cell), 3)]


def _count_match_at(board, active, r, c, color):
    """Count how many in a row/col match 'color' starting from (r,c) after a hypothetical swap."""
    rows = len(board)
    cols = len(board[0]) if rows else 0

    def is_match(rr, cc_):
        return (0 <= rr < rows and 0 <= cc_ < cols
                and active[rr][cc_]
                and board[rr][cc_] == color)

    # Horizontal run
    h = 1
    cc_ = c - 1
    while cc_ >= 0 and is_match(r, cc_):
        h += 1; cc_ -= 1
    cc_ = c + 1
    while cc_ < cols and is_match(r, cc_):
        h += 1; cc_ += 1

    # Vertical run
    v = 1
    rr = r - 1
    while rr >= 0 and is_match(rr, c):
        v += 1; rr -= 1
    rr = r + 1
    while rr < rows and is_match(rr, c):
        v += 1; rr += 1

    return max(h, v)


def _simulate_swap(board, r1, c1, r2, c2):
    """Return a new board with cells (r1,c1) and (r2,c2) swapped."""
    new = [row[:] for row in board]
    new[r1][c1], new[r2][c2] = new[r2][c2], new[r1][c1]
    return new


def _score_swap(board, active, r1, c1, r2, c2):
    """
    Score a swap: returns total match-run length if it creates ≥3 matches, else 0.
    Same-color swaps are always invalid (board unchanged, no new match possible).
    """
    if board[r1][c1] == board[r2][c2]:
        return 0
    new_board = _simulate_swap(board, r1, c1, r2, c2)
    score = 0
    for (r, c) in [(r1, c1), (r2, c2)]:
        color = new_board[r][c]
        if color in _UNMOVABLE:
            continue
        run = _count_match_at(new_board, active, r, c, color)
        if run >= 3:
            score += run
    return score


def find_best_move(board: list[list[str]],
                   tilemap_rows: list[list[str]],
                   blacklisted: set | None = None) -> tuple[int,int,int,int] | None:
    """
    Find the best adjacent swap move.

    Returns (r1, c1, r2, c2) of the swap that creates the highest-scoring match,
    or None if no valid move found.
    Swaps are only between horizontally or vertically adjacent swappable cells.
    Moves in the blacklisted set are skipped.
    """
    active    = _active_mask(tilemap_rows)
    swappable = _swappable_mask(tilemap_rows)
    rows = len(board)
    cols = len(board[0]) if rows else 0

    best_score = 0
    best_move = None

    for r in range(rows):
        for c in range(cols):
            if not swappable[r][c] or board[r][c] in _UNMOVABLE:
                continue
            # Try right swap
            if c + 1 < cols and swappable[r][c + 1] and board[r][c + 1] not in _UNMOVABLE:
                candidate = (r, c, r, c + 1)
                if blacklisted and candidate in blacklisted:
                    continue
                sc = _score_swap(board, active, r, c, r, c + 1)
                if sc > best_score:
                    best_score = sc
                    best_move = candidate
            # Try down swap
            if r + 1 < rows and swappable[r + 1][c] and board[r + 1][c] not in _UNMOVABLE:
                candidate = (r, c, r + 1, c)
                if blacklisted and candidate in blacklisted:
                    continue
                sc = _score_swap(board, active, r, c, r + 1, c)
                if sc > best_score:
                    best_score = sc
                    best_move = candidate

    return best_move


def find_any_move(board: list[list[str]],
                  tilemap_rows: list[list[str]],
                  blacklisted: set | None = None) -> tuple[int,int,int,int] | None:
    """
    Find any valid move (≥3 match), returning the first one found.
    Used as fallback when find_best_move returns None (shouldn't happen in normal play).
    Moves in the blacklisted set are skipped.
    """
    active    = _active_mask(tilemap_rows)
    swappable = _swappable_mask(tilemap_rows)
    rows = len(board)
    cols = len(board[0]) if rows else 0

    for r in range(rows):
        for c in range(cols):
            if not swappable[r][c] or board[r][c] in _UNMOVABLE:
                continue
            for (r2, c2) in [(r, c+1), (r+1, c)]:
                if (0 <= r2 < rows and 0 <= c2 < cols
                        and swappable[r2][c2]
                        and board[r2][c2] not in _UNMOVABLE):
                    candidate = (r, c, r2, c2)
                    if blacklisted and candidate in blacklisted:
                        continue
                    sc = _score_swap(board, active, r, c, r2, c2)
                    if sc > 0:
                        return candidate
    return None
