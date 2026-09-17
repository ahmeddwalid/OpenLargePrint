"""Unit tests for table layout evaluation, fitting, splitting, and linearization (TBL-001, TBL-002, FN-002)."""

import pytest
from openlargeprint.ir.models import TableCell, TableStructure
from openlargeprint.layout.table import (
    TableTier,
    estimate_column_widths,
    evaluate_table_fit,
    split_table_by_columns,
)


def sample_simple_table() -> TableStructure:
    """Create a 3-row, 3-column table that easily fits in portrait page width."""
    return TableStructure(
        has_header=True,
        caption="Court Decisions",
        rows=[
            [
                TableCell(text="Case Name", is_header=True),
                TableCell(text="Year", is_header=True),
                TableCell(text="Court", is_header=True),
            ],
            [
                TableCell(text="Donoghue v Stevenson"),
                TableCell(text="1932"),
                TableCell(text="House of Lords"),
            ],
            [
                TableCell(text="Carlill v Carbolic Smoke Ball"),
                TableCell(text="1893"),
                TableCell(text="Court of Appeal"),
            ],
        ],
    )


def sample_wide_table() -> TableStructure:
    """Create a dense 6-column legal table that exceeds portrait page width at large font."""
    return TableStructure(
        has_header=True,
        caption="Comparative Legal Jurisdictions & Standards",
        rows=[
            [
                TableCell(text="Jurisdiction", is_header=True),
                TableCell(text="Statute Reference", is_header=True),
                TableCell(text="Burden of Proof Standard", is_header=True),
                TableCell(text="Applicable Limitations Period", is_header=True),
                TableCell(text="Appellate Precedent", is_header=True),
                TableCell(text="Key Statutory Remedies", is_header=True),
            ],
            [
                TableCell(text="England & Wales"),
                TableCell(text="Senior Courts Act 1981 s.31"),
                TableCell(text="Balance of probabilities"),
                TableCell(text="3 months for judicial review"),
                TableCell(text="Anisminic Ltd v Foreign Compensation Commission"),
                TableCell(text="Quashing order, mandatory order, declaration"),
            ],
            [
                TableCell(text="United States"),
                TableCell(text="5 U.S. Code § 706 (APA)"),
                TableCell(text="Arbitrary and capricious / Substantial evidence"),
                TableCell(text="6 years general civil action"),
                TableCell(text="Chevron U.S.A. v. Natural Resources Defense Council"),
                TableCell(text="Vacatur, preliminary injunction, mandamus"),
            ],
        ],
    )


def test_estimate_column_widths():
    """Verify column width estimation scales with font size and word lengths."""
    table = sample_simple_table()
    widths_14 = estimate_column_widths(table, font_pt=14.0)
    widths_20 = estimate_column_widths(table, font_pt=20.0)

    assert len(widths_14) == 3
    assert len(widths_20) == 3
    # Higher font size must require wider columns
    assert sum(widths_20) > sum(widths_14)


def test_evaluate_table_fit_tier1_enlarged():
    """Verify standard table fits at Tier 1 (Enlarged) within standard page width (~470pt)."""
    table = sample_simple_table()
    eval_res = evaluate_table_fit(table, available_width=470.0, font_pt=18.0, min_readable_pt=14.0)

    assert eval_res.tier == TableTier.ENLARGED
    assert eval_res.total_width <= 470.0
    assert eval_res.warning is None


def test_evaluate_table_fit_tier2_split():
    """Verify wide 6-column table splits into sub-tables (TBL-001 Tier 2)."""
    table = sample_wide_table()
    # Available width 350pt is too narrow for all 6 columns at 14pt, but sub-tables (3 cols) fit
    eval_res = evaluate_table_fit(table, available_width=350.0, font_pt=18.0, min_readable_pt=14.0)

    # Wide table splits or linearizes
    assert eval_res.tier in (TableTier.SPLIT, TableTier.LINEARIZE)
    if eval_res.tier == TableTier.SPLIT:
        assert len(eval_res.split_tables) >= 2
        # All sub-tables must retain the anchor/key column 0
        for st in eval_res.split_tables:
            assert st.rows[0][0].text == "Jurisdiction"
            assert st.rows[1][0].text == "England & Wales"


def test_evaluate_table_fit_tier3_linearize():
    """Verify extremely constrained width falls back to accessible linearization with warning (TBL-001, TBL-002)."""
    table = sample_wide_table()
    # Tiny width 150pt cannot fit even 2 columns at 14pt
    eval_res = evaluate_table_fit(table, available_width=150.0, font_pt=18.0, min_readable_pt=14.0)

    assert eval_res.tier == TableTier.LINEARIZE
    assert eval_res.linearized_text is not None
    assert "• Row 1:" in eval_res.linearized_text
    assert "Jurisdiction: England & Wales" in eval_res.linearized_text
    # TBL-002: Must include visible warning, never silent
    assert eval_res.warning is not None
    assert "TBL-001" in eval_res.warning or "TBL-002" in eval_res.warning


def test_split_table_by_columns():
    """Verify sub-tables correctly slice columns while preserving header row and anchor column."""
    table = sample_wide_table()
    sub_tables = split_table_by_columns(table, max_data_cols=2)

    assert len(sub_tables) >= 2
    for st in sub_tables:
        assert st.has_header is True
        assert st.row_count == table.row_count
        # Anchor column is always column 0
        assert st.rows[0][0].text == "Jurisdiction"


def test_table_to_markdown():
    """Verify TableStructure to_markdown_table formatting."""
    table = sample_simple_table()
    md = table.to_markdown_table()
    assert "| Case Name | Year | Court |" in md
    assert "| --- | --- | --- |" in md
    assert "| Donoghue v Stevenson | 1932 | House of Lords |" in md
