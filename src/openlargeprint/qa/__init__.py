"""Quality assurance, evaluation metrics, and rights-safe benchmark suite (QA-001..003, PERF-002)."""

from openlargeprint.qa.metrics import (
    calculate_cer,
    calculate_wer,
    calculate_reading_order_accuracy,
    calculate_table_structural_score,
    calculate_image_retention,
    calculate_page_anchor_fidelity,
    EvaluationMetrics,
)
from openlargeprint.qa.corpus_builder import BenchmarkCorpusBuilder
from openlargeprint.qa.benchmark import BenchmarkCase, BenchmarkReport, BenchmarkRunner

__all__ = [
    "calculate_cer",
    "calculate_wer",
    "calculate_reading_order_accuracy",
    "calculate_table_structural_score",
    "calculate_image_retention",
    "calculate_page_anchor_fidelity",
    "EvaluationMetrics",
    "BenchmarkCorpusBuilder",
    "BenchmarkCase",
    "BenchmarkReport",
    "BenchmarkRunner",
]
