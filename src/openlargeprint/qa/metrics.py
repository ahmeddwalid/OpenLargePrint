"""Evaluation metrics implementation: CER, WER, reading order, table score, image retention (QA-002)."""

from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute standard Levenshtein edit distance between two sequences."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculate Character Error Rate (CER = edit_dist / len(ref))."""
    ref_clean = reference.strip()
    hyp_clean = hypothesis.strip()

    if not ref_clean and not hyp_clean:
        return 0.0
    if not ref_clean:
        return 1.0

    dist = _levenshtein_distance(ref_clean, hyp_clean)
    return min(1.0, dist / len(ref_clean))


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate (WER = word_edit_dist / len(ref_words))."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()

    if not ref_words and not hyp_words:
        return 0.0
    if not ref_words:
        return 1.0

    matcher = difflib.SequenceMatcher(None, ref_words, hyp_words)
    # WER can be computed from operations
    dist = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            dist += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            dist += i2 - i1
        elif tag == "insert":
            dist += j2 - j1

    return min(1.0, dist / len(ref_words))


def calculate_reading_order_accuracy(ref_order: List[str], hyp_order: List[str]) -> float:
    """Calculate Reading Order Accuracy using normalized Longest Common Subsequence (LCS)."""
    if not ref_order and not hyp_order:
        return 1.0
    if not ref_order or not hyp_order:
        return 0.0

    matcher = difflib.SequenceMatcher(None, ref_order, hyp_order)
    match_size = sum(block.size for block in matcher.get_matching_blocks())
    return match_size / len(ref_order)


def calculate_table_structural_score(
    ref_table: List[List[str]],
    hyp_table: List[List[str]],
) -> float:
    """Calculate Table Structure Score based on row/column counts and cell content overlap."""
    if not ref_table and not hyp_table:
        return 1.0
    if not ref_table or not hyp_table:
        return 0.0

    ref_rows = len(ref_table)
    hyp_rows = len(hyp_table)
    ref_cols = max(len(r) for r in ref_table) if ref_table else 0
    hyp_cols = max(len(r) for r in hyp_table) if hyp_table else 0

    row_score = max(0.0, 1.0 - abs(ref_rows - hyp_rows) / max(1, ref_rows))
    col_score = max(0.0, 1.0 - abs(ref_cols - hyp_cols) / max(1, ref_cols))

    # Cell content accuracy
    matching_cells = 0
    total_cells = 0
    for r in range(min(ref_rows, hyp_rows)):
        for c in range(min(len(ref_table[r]), len(hyp_table[r]))):
            total_cells += 1
            if ref_table[r][c].strip().lower() == hyp_table[r][c].strip().lower():
                matching_cells += 1

    content_score = (matching_cells / total_cells) if total_cells > 0 else 0.0

    # Weighted composite score: 30% row alignment, 30% col alignment, 40% cell contents
    return round(0.3 * row_score + 0.3 * col_score + 0.4 * content_score, 3)


def calculate_image_retention(ref_count: int, hyp_count: int) -> float:
    """Calculate Image Retention Rate."""
    if ref_count == 0:
        return 1.0 if hyp_count == 0 else 1.0
    return min(1.0, hyp_count / ref_count)


def calculate_page_anchor_fidelity(ref_pages: List[int], hyp_pages: List[int]) -> float:
    """Calculate Page Anchor Fidelity (presence of expected source page anchors)."""
    if not ref_pages:
        return 1.0
    found = sum(1 for p in ref_pages if p in hyp_pages)
    return found / len(ref_pages)


class EvaluationMetrics(BaseModel):
    """Container for multi-dimensional quality metrics (QA-002, PERF-002)."""

    cer: float = Field(..., ge=0.0, le=1.0, description="Character Error Rate")
    wer: float = Field(..., ge=0.0, le=1.0, description="Word Error Rate")
    reading_order_score: float = Field(..., ge=0.0, le=1.0, description="Reading order correctness")
    table_score: float = Field(..., ge=0.0, le=1.0, description="Table structure fidelity")
    image_retention: float = Field(..., ge=0.0, le=1.0, description="Asset retention rate")
    page_anchor_fidelity: float = Field(..., ge=0.0, le=1.0, description="Source page reference preservation")
    speed_sec_per_page: float = Field(..., ge=0.0, description="Execution speed in seconds per page")
    peak_ram_mb: float = Field(..., ge=0.0, description="Peak memory consumed in megabytes")
