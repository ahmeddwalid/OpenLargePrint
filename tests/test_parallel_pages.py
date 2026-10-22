"""Pages converted side by side give the same document as one at a time (PERF-001)."""

from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from openlargeprint import runtime
from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.security.isolation import JobWorkspace


def _book(path: Path, pages: int = 5) -> Path:
    c = canvas.Canvas(str(path), pagesize=A4)
    for page in range(pages):
        c.setFont("Helvetica-Bold", 18)
        c.drawString(72, 770, f"Chapter {page + 1}")
        c.setFont("Helvetica", 11)
        for line in range(12):
            c.drawString(72, 730 - line * 18, f"Page {page + 1} line {line + 1}: the parties agree to the terms set out.")
        c.showPage()
    c.save()
    return path


def _convert(pdf: Path, monkeypatch, workers: int, cancel_after: int | None = None):
    monkeypatch.setenv("OLP_PAGE_WORKERS", str(workers))
    seen = []

    def progress(done, total, stage, message):
        seen.append(done)

    cancel = (lambda: len(seen) >= cancel_after) if cancel_after else None
    with JobWorkspace() as workspace:
        doc = NativePdfImporter().import_document(pdf, workspace, progress_callback=progress, cancel_check=cancel)
    return doc, seen


def test_parallel_pages_match_one_at_a_time(tmp_path: Path, monkeypatch):
    pdf = _book(tmp_path / "book.pdf")
    one, _ = _convert(pdf, monkeypatch, 1)
    two, progress = _convert(pdf, monkeypatch, 2)
    assert [(b.type, b.text, b.source_page) for b in two.blocks] == \
           [(b.type, b.text, b.source_page) for b in one.blocks]
    assert [p.page_number for p in two.pages] == [1, 2, 3, 4, 5]
    assert progress[-1] == 5


def test_cancelling_stops_parallel_pages(tmp_path: Path, monkeypatch):
    pdf = _book(tmp_path / "book.pdf", pages=8)
    with pytest.raises(InterruptedError):
        _convert(pdf, monkeypatch, 2, cancel_after=1)


def test_worker_counts_follow_cores_memory_and_page_type(monkeypatch):
    monkeypatch.delenv("OLP_PAGE_WORKERS", raising=False)
    monkeypatch.setattr(runtime, "cpu_count", lambda: 8)
    monkeypatch.setattr(runtime, "available_memory_gb", lambda: 32.0)
    assert runtime.page_workers(100, scanned_share=1.0) == 4
    assert runtime.page_workers(100, scanned_share=0.0) == 2
    assert runtime.page_workers(2, scanned_share=1.0) == 2
    monkeypatch.setattr(runtime, "available_memory_gb", lambda: 3.0)
    assert runtime.page_workers(100, scanned_share=1.0) == 1  # not enough memory for two
    monkeypatch.setenv("OLP_PAGE_WORKERS", "1")
    assert runtime.page_workers(100, scanned_share=1.0) == 1
    assert runtime.threads_for_workers(4, scanned_share=1.0) == 1
    assert runtime.threads_for_workers(2, scanned_share=0.0) == 4


def test_graphics_card_is_never_used_off_windows(monkeypatch):
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    runtime.gpu_ready.cache_clear()
    monkeypatch.setenv("OLP_GPU", "auto")
    assert runtime.providers() == ["CPUExecutionProvider"]
    runtime.gpu_ready.cache_clear()


def test_graphics_card_check_declines_a_device_that_is_not_faster(monkeypatch):
    """The check runs the detector twice; a "graphics card" that is the CPU again is not used."""
    from openlargeprint.models import model_manager
    monkeypatch.setattr(runtime, "DML", "CPUExecutionProvider")
    path = str(model_manager.get_model_path("PP-OCRv6_det_small", verify=True))
    assert runtime._probe_directml(path) is False
