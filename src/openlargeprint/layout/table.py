"""Table layout fitting and large-print adaptation engine (TBL-001, TBL-002, FN-002).

Implements the 3-tier presentation cascade for large-print documents:
- Tier 1: Enlarged semantic table (respects minimum readable font >= 14pt).
- Tier 2: Landscape / split column sub-tables (preserves key anchor column).
- Tier 3: Accessible labeled linearization (card-per-row) with visible warning.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from openlargeprint.ir.models import TableCell, TableStructure


class TableTier(str, Enum):
    """Presentation tier selected based on table width and target printable area."""
    ENLARGED = "enlarged"
    SPLIT = "split"
    LINEARIZE = "linearize"


class TableFitEvaluation(BaseModel):
    """Results of evaluating table fit against available page width."""
    tier: TableTier
    column_widths: List[float]
    total_width: float
    available_width: float
    split_tables: List[TableStructure] = Field(default_factory=list)
    linearized_text: Optional[str] = None
    warning: Optional[str] = None


def estimate_column_widths(
    table: TableStructure,
    font_pt: float,
    padding_pt: float = 16.0,
    min_col_width: float = 60.0,
) -> List[float]:
    """Estimate required width in points for each column in the table.
    
    Uses proportional character width modeling (approx 0.55 * font_pt per character)
    and accounts for padding and word-wrap minimums.
    """
    if not table.rows:
        return []

    col_count = table.column_count
    char_width = font_pt * 0.55

    col_max_chars: List[int] = [0] * col_count
    col_longest_words: List[int] = [0] * col_count

    for row in table.rows:
        for c_idx, cell in enumerate(row):
            if c_idx >= col_count:
                break
            text = (cell.text or "").strip()
            lines = text.split("\n")
            for line in lines:
                col_max_chars[c_idx] = max(col_max_chars[c_idx], len(line))
            for word in text.split():
                col_longest_words[c_idx] = max(col_longest_words[c_idx], len(word))

    col_widths: List[float] = []
    for c_idx in range(col_count):
        # Column width needs to fit at least the longest unbroken word plus padding
        min_word_w = (col_longest_words[c_idx] * char_width) + padding_pt
        # Proportional width based on average/max line length (capped to reasonable ceiling)
        avg_line_w = (min(col_max_chars[c_idx], 20) * char_width) + padding_pt
        w = max(min_col_width, min_word_w, avg_line_w)
        col_widths.append(round(w, 2))

    return col_widths


def split_table_by_columns(
    table: TableStructure,
    max_data_cols: int = 2,
) -> List[TableStructure]:
    """Split a wide table into smaller sub-tables sharing the leading anchor column (TBL-001).
    
    For example, a 5-column table [Col0, Col1, Col2, Col3, Col4] is split into:
    - Sub-table 1: [Col0, Col1, Col2]
    - Sub-table 2: [Col0, Col3, Col4]
    """
    if table.column_count <= max_data_cols + 1 or not table.rows:
        return [table]

    sub_tables: List[TableStructure] = []
    total_cols = table.column_count

    col_slices: List[List[int]] = []
    curr_slice: List[int] = [0]  # Anchor column always included

    for c in range(1, total_cols):
        curr_slice.append(c)
        if len(curr_slice) == max_data_cols + 1:
            col_slices.append(curr_slice)
            curr_slice = [0]

    if len(curr_slice) > 1:
        col_slices.append(curr_slice)

    for slice_idx, cols in enumerate(col_slices, start=1):
        sub_rows: List[List[TableCell]] = []
        for row in table.rows:
            sub_row: List[TableCell] = []
            for c in cols:
                if c < len(row):
                    sub_row.append(row[c])
                else:
                    sub_row.append(TableCell(text=""))
            sub_rows.append(sub_row)

        sub_caption = (
            f"{table.caption or 'Table'} (Part {slice_idx} of {len(col_slices)})"
            if table.caption
            else f"Table (Part {slice_idx} of {len(col_slices)})"
        )
        sub_tables.append(
            TableStructure(
                rows=sub_rows,
                has_header=table.has_header,
                caption=sub_caption,
            )
        )

    return sub_tables


def evaluate_table_fit(
    table: TableStructure,
    available_width: float,
    font_pt: float,
    min_readable_pt: float = 14.0,
) -> TableFitEvaluation:
    """Evaluate table dimensions against available page width and choose presentation tier.
    
    Follows TBL-001 / TBL-002:
    1. Tier 1: Enlarged semantic table if width fits at font_pt or scaled down to >= min_readable_pt.
    2. Tier 2: Split columns if table has >= 4 columns and can be split cleanly.
    3. Tier 3: Linearized accessible cards + visible warning if too dense for tabular columns.
    """
    if not table.rows:
        return TableFitEvaluation(
            tier=TableTier.ENLARGED,
            column_widths=[],
            total_width=0.0,
            available_width=available_width,
        )

    # 1. Check fit at requested large font size
    est_widths = estimate_column_widths(table, font_pt)
    total_w = sum(est_widths)

    if total_w <= available_width:
        # Fits comfortably at full font_pt
        return TableFitEvaluation(
            tier=TableTier.ENLARGED,
            column_widths=est_widths,
            total_width=total_w,
            available_width=available_width,
        )

    # 2. Check fit at enforced minimum readable font size (FN-002: >= 14pt)
    min_widths = estimate_column_widths(table, min_readable_pt)
    min_total_w = sum(min_widths)

    if min_total_w <= available_width:
        # Scale smoothly between min_widths and est_widths to fit available_width
        surplus = available_width - min_total_w
        demand = max(1.0, total_w - min_total_w)
        scale = min(1.0, max(0.0, surplus / demand))
        scaled_widths = [round(min_w + (w - min_w) * scale, 2) for w, min_w in zip(est_widths, min_widths)]
        return TableFitEvaluation(
            tier=TableTier.ENLARGED,
            column_widths=scaled_widths,
            total_width=sum(scaled_widths),
            available_width=available_width,
        )

    # 3. If table has 4 or more columns, attempt Tier 2: Split columns (TBL-001)
    if table.column_count >= 4:
        split_tables = split_table_by_columns(table, max_data_cols=2)
        # Check if sub-tables fit
        sub_fit_ok = True
        for st in split_tables:
            sub_w = sum(estimate_column_widths(st, min_readable_pt))
            if sub_w > available_width * 1.15:  # Tolerance threshold
                sub_fit_ok = False
                break

        if sub_fit_ok:
            return TableFitEvaluation(
                tier=TableTier.SPLIT,
                column_widths=min_widths,
                total_width=min_total_w,
                available_width=available_width,
                split_tables=split_tables,
                warning="Table split across sub-tables to maintain large-print readability (TBL-001)",
            )

    # 4. Fall back to Tier 3: Accessible Linearized Representation (TBL-001, TBL-002)
    linearized = table.to_linearized_text()
    warning_msg = (
        f"Table with {table.column_count} columns linearized: column widths exceed page width "
        f"at minimum readable {min_readable_pt}pt size (TBL-001, TBL-002)"
    )
    return TableFitEvaluation(
        tier=TableTier.LINEARIZE,
        column_widths=min_widths,
        total_width=min_total_w,
        available_width=available_width,
        linearized_text=linearized,
        warning=warning_msg,
    )
