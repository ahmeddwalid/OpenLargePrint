"""Layout adaptation, fitting, and structural reflow engines for OpenLargePrint."""

from openlargeprint.layout.table import (
    TableFitEvaluation,
    TableTier,
    estimate_column_widths,
    evaluate_table_fit,
    split_table_by_columns,
)

__all__ = [
    "TableFitEvaluation",
    "TableTier",
    "estimate_column_widths",
    "evaluate_table_fit",
    "split_table_by_columns",
]
