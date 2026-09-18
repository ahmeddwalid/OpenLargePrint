"""Tests for evaluation metrics and rights-safe benchmark corpus runner (QA-001..003, PERF-002)."""

from pathlib import Path
import pytest

from openlargeprint.qa import (
    BenchmarkCorpusBuilder,
    BenchmarkReport,
    BenchmarkRunner,
    calculate_cer,
    calculate_image_retention,
    calculate_page_anchor_fidelity,
    calculate_reading_order_accuracy,
    calculate_table_structural_score,
    calculate_wer,
)


def test_cer_and_wer_metrics():
    """Verify Character Error Rate and Word Error Rate calculation."""
    # Exact match
    assert calculate_cer("Hello world", "Hello world") == 0.0
    assert calculate_wer("Hello world", "Hello world") == 0.0

    # Single character difference
    cer = calculate_cer("Hello world", "Hella world")
    assert 0.0 < cer <= 0.15

    # Single word substitution
    wer = calculate_wer("The court affirmed the decision", "The court reversed the decision")
    assert 0.15 <= wer <= 0.25

    # Empty cases
    assert calculate_cer("", "") == 0.0
    assert calculate_wer("", "") == 0.0
    assert calculate_cer("abc", "") == 1.0


def test_reading_order_and_table_metrics():
    """Verify reading order accuracy and table structural scoring."""
    ref_order = ["b1", "b2", "b3", "b4", "b5"]
    assert calculate_reading_order_accuracy(ref_order, ref_order) == 1.0
    # Reversed / swapped order
    permuted = ["b1", "b3", "b2", "b4", "b5"]
    assert calculate_reading_order_accuracy(ref_order, permuted) < 1.0

    ref_table = [
        ["Section", "Requirement"],
        ["§ 101", "Patentable subject matter"],
        ["§ 102", "Novelty requirement"],
    ]
    hyp_table_exact = [
        ["Section", "Requirement"],
        ["§ 101", "Patentable subject matter"],
        ["§ 102", "Novelty requirement"],
    ]
    assert calculate_table_structural_score(ref_table, hyp_table_exact) == 1.0

    hyp_table_diff = [
        ["Section", "Requirement"],
        ["§ 101", "Wrong text"],
    ]
    assert calculate_table_structural_score(ref_table, hyp_table_diff) <= 0.8


def test_benchmark_corpus_builder(tmp_path: Path):
    """Verify all 16 benchmark test cases are synthesized without copyright issues (QA-001)."""
    builder = BenchmarkCorpusBuilder(tmp_path)
    cases = builder.build_all()
    assert len(cases) == 16

    expected_keys = [
        "born_digital_english",
        "two_column_law",
        "legal_footnotes",
        "scanned_english",
        "arabic_scan",
        "mixed_bidi",
        "scanned_table",
        "images_captions",
        "rotated_page",
        "skewed_page",
        "low_res_scan",
        "mixed_digital_scan",
        "page_numbering",
        "malformed_pdf",
        "docx_sample",
        "pptx_sample",
    ]

    for key in expected_keys:
        assert key in cases
        assert cases[key].exists()
        assert cases[key].stat().st_size > 0


def test_benchmark_runner_end_to_end(tmp_path: Path):
    """Verify BenchmarkRunner executes and generates structured multi-metric report (QA-002, PERF-002)."""
    runner = BenchmarkRunner(corpus_dir=tmp_path / "corpus")
    # Generate and run the benchmark suite
    report = runner.run_benchmark(out_dir=tmp_path / "results")

    assert isinstance(report, BenchmarkReport)
    assert report.total_cases == 16
    assert report.passed_cases == 16
    assert report.failed_cases == 0

    # Ensure individual metrics are recorded
    assert "born_digital_english" in report.results
    res = report.results["born_digital_english"]
    assert res.success
    assert res.metrics.cer == 0.0
    assert res.metrics.reading_order_score == 1.0

    # Ensure table report formatting works
    md_table = report.to_markdown_table()
    assert "| Case Name | Format |" in md_table
    assert "born_digital_english" in md_table
    assert "PASS" in md_table
