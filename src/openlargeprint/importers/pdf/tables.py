"""Table structure from words inside a detected table region (TBL-001, TBL-002).

Columns come from ruling lines when the table has them, otherwise from the
vertical white space that runs through every row. Rows come from horizontal
rules when present; without rules, a line whose first column is empty is a
continuation of the row above (a wrapped cell). The result keeps every word;
when the grid is doubtful the caller shows the source table next to it.
"""

from __future__ import annotations

import statistics
from typing import List, Optional, Sequence, Tuple

from openlargeprint.ir.models import TableCell, TableStructure
from openlargeprint.layout.regions import LayoutRegion
from .rules import Rule
from .textlayer import Word


def _rows(words: Sequence[Word]) -> List[List[Word]]:
    rows: List[List[Word]] = []
    for word in sorted(words, key=lambda w: (w.cy, w.x0)):
        for row in reversed(rows[-3:]):
            mid = statistics.median(w.cy for w in row)
            if abs(word.cy - mid) <= 0.45 * max(word.size, row[0].size):
                row.append(word)
                break
        else:
            rows.append([word])
    for row in rows:
        row.sort(key=lambda w: w.x0)
    rows.sort(key=lambda r: min(w.y0 for w in r))
    return rows


def _column_edges(rows: List[List[Word]], region: LayoutRegion, vertical: Sequence[Rule], size: float) -> List[float]:
    """Separator x positions between columns."""
    inner = [r.x for r in vertical
             if region.x0 + 4 < r.x < region.x1 - 4 and r.length > 0.5 * region.height]
    if inner:
        merged: List[float] = []
        for x in sorted(inner):
            if not merged or x - merged[-1] > 2 * size:
                merged.append(x)
        return merged
    # White space shared by (nearly) every row.
    step = 1.0
    width = int((region.x1 - region.x0) / step) + 1
    if width <= 2:
        return []
    covered = [0] * width
    for row in rows:
        marks = [False] * width
        for w in row:
            a = max(0, int((w.x0 - region.x0) / step))
            b = min(width - 1, int((w.x1 - region.x0) / step))
            for i in range(a, b + 1):
                marks[i] = True
        for i, m in enumerate(marks):
            covered[i] += m
    limit = max(0, int(0.08 * len(rows)))
    min_gap = max(4.0, 0.9 * size)
    edges: List[float] = []
    start = None
    first = next((i for i, c in enumerate(covered) if c), 0)
    last = max((i for i, c in enumerate(covered) if c), default=width - 1)
    for i in range(first, last + 1):
        if covered[i] <= limit:
            if start is None:
                start = i
        elif start is not None:
            if (i - start) * step >= min_gap:
                edges.append(region.x0 + (start + i) / 2 * step)
            start = None
    return edges


def build_table(region: LayoutRegion, words: List[Word], rules: Sequence[Rule]) -> Optional[Tuple[TableStructure, float]]:
    real = [w for w in words if w.text.strip()]
    if len(real) < 4:
        return None
    size = statistics.median(w.size for w in real)
    vertical = [r for r in rules if r.vertical]
    # A row rule is often broken where it touches letters; collinear pieces count together.
    by_y: List[List[Rule]] = []
    for r in sorted((r for r in rules if not r.vertical and region.y0 - 2 <= r.y <= region.y1 + 2
                     and r.x1 > region.x0 and r.x0 < region.x1), key=lambda r: r.y):
        if by_y and abs(by_y[-1][-1].y - r.y) <= 1.2:
            by_y[-1].append(r)
        else:
            by_y.append([r])
    horizontal = [Rule(min(r.x0 for r in g), min(r.y0 for r in g), max(r.x1 for r in g), max(r.y1 for r in g))
                  for g in by_y if sum(r.length for r in g) > 0.5 * region.width]
    rows = _rows(real)
    edges = _column_edges(rows, region, vertical, size)
    if not edges:
        return None
    columns = len(edges) + 1

    def column_of(word: Word) -> int:
        return sum(1 for e in edges if word.cx > e)

    grid: List[List[List[Word]]] = []
    row_tops: List[float] = []
    ruled = len(horizontal) >= 2
    separators = sorted(r.y for r in horizontal)
    for row in rows:
        cells: List[List[Word]] = [[] for _ in range(columns)]
        for w in row:
            cells[column_of(w)].append(w)
        top = min(w.y0 for w in row)
        if grid:
            prev_bottom = max(w.y1 for c in grid[-1] for w in c)
            crosses_rule = any(prev_bottom - 1 <= y <= top + 1 for y in separators)
            header_break = len(grid) == 1 and all(w.bold for c in grid[0] for w in c) and not all(w.bold for w in row)
            if header_break:
                continuation = False
            elif ruled:
                continuation = not crosses_rule
            else:
                gap = top - prev_bottom
                continuation = (not cells[0]) and any(cells[1:]) and gap < 0.9 * size
            if continuation:
                for i in range(columns):
                    grid[-1][i].extend(cells[i])
                continue
        grid.append(cells)
        row_tops.append(top)

    if len(grid) == 1 and sum(1 for cell in grid[0] if cell) >= 2:
        # A table to fill in: printed headings over empty ruled rows.
        below = [y for y in separators if y > max(w.y1 for c in grid[0] for w in c) + 2]
        empty_rows = max(1, min(8, len(below) - 1))
        structure = TableStructure(
            rows=[[TableCell(text=" ".join(w.text for w in sorted(cell, key=lambda w: w.x0)), is_header=True)
                   for cell in grid[0]]] + [[TableCell(text="") for _ in range(columns)] for _ in range(empty_rows)],
            has_header=True,
        )
        return structure, 0.8
    if len(grid) < 2:
        return None
    filled = sum(1 for row in grid for cell in row if cell)
    density = filled / (len(grid) * columns)
    header_bold = all(all(w.bold for w in cell) for cell in grid[0] if cell) and any(grid[0])
    body_bold = sum(1 for row in grid[1:] for cell in row for w in cell if w.bold)
    body_total = sum(1 for row in grid[1:] for cell in row for w in cell)
    has_header = header_bold and body_bold < 0.8 * max(1, body_total)

    def cell_text(cell: List[Word]) -> str:
        lines: List[List[Word]] = []
        for w in sorted(cell, key=lambda w: (w.cy, w.x0)):
            if lines and abs(w.cy - statistics.median(x.cy for x in lines[-1])) <= 0.45 * w.size:
                lines[-1].append(w)
            else:
                lines.append([w])
        return " ".join(" ".join(x.text for x in sorted(line, key=lambda w: w.x0)) for line in lines)

    structure = TableStructure(
        rows=[[TableCell(text=cell_text(cell), is_header=has_header and r == 0) for cell in row]
              for r, row in enumerate(grid)],
        has_header=has_header,
    )
    confidence = 0.9 if (vertical or ruled) else (0.8 if density >= 0.6 else 0.55)
    confidence = min(confidence, min(w.confidence for w in real))
    return structure, confidence


def ruled_table_regions(rules: Sequence[Rule], words: Sequence[Word]) -> List[LayoutRegion]:
    """Grids drawn with ruling lines, used when no layout model is available (TBL-001).

    Only an unmistakable grid counts: at least three vertical rules spanning the
    same height (two outer edges and a column separator), at least two
    horizontal rules across them, and words in at least two rows inside.
    Anything less stays ordinary text, so prose is never turned into a table.
    """
    from openlargeprint.layout.regions import RegionKind

    vertical = sorted((r for r in rules if r.vertical), key=lambda r: r.x)
    groups: List[List[Rule]] = []
    for rule in vertical:
        for group in groups:
            if abs(group[0].y0 - rule.y0) <= 4 and abs(group[0].y1 - rule.y1) <= 4:
                group.append(rule)
                break
        else:
            groups.append([rule])
    regions: List[LayoutRegion] = []
    for group in groups:
        if len(group) < 3:
            continue
        x0, x1 = min(r.x0 for r in group), max(r.x1 for r in group)
        y0, y1 = min(r.y0 for r in group), max(r.y1 for r in group)
        across = [r for r in rules if not r.vertical and y0 - 3 <= r.y <= y1 + 3
                  and r.x0 <= x0 + 6 and r.x1 >= x1 - 6]
        if len(across) < 2:
            continue
        inside = [w for w in words if x0 <= w.cx <= x1 and y0 <= w.cy <= y1 and w.text.strip()]
        if not inside or len(_rows(inside)) < 2:
            continue
        regions.append(LayoutRegion(RegionKind.TABLE, x0, y0, x1, y1, score=0.5, label="ruled_table"))
    return regions
