"""Benchmark runner and quality reporter tracking multi-dimensional metrics (QA-001..003, PERF-002)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


import tempfile

from openlargeprint.ir.models import BlockType, DocumentIR
from openlargeprint.pipeline import PipelineOrchestrator
from openlargeprint.qa.corpus_builder import BenchmarkCorpusBuilder
from openlargeprint.qa.metrics import (
    EvaluationMetrics,
    calculate_cer,
    calculate_image_retention,
    calculate_wer,
)


def get_current_ram_mb() -> float:
    """Cross-platform peak/working-set memory retrieval (PERF-002)."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except ImportError:
        # Windows API fallback via ctypes (PERF-002).
        # GetProcessMemoryInfo must be declared with explicit argtypes/restype: a process
        # handle passed with ctypes' default C int truncates to 32 bits, the call fails,
        # and this function then silently reports 0.0 MB, which makes every performance
        # number in the reports meaningless.
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.PeakWorkingSetSize / (1024.0 * 1024.0)
        except Exception:
            pass
        return 0.0


def _reading_order_plausibility(doc: DocumentIR) -> float:
    """Score how well block order follows page order and top-to-bottom geometry.

    Unlike comparing a sequence to itself, this actually detects scrambled
    reading order: every consecutive content-block pair must not move backwards
    in page number or vertically within a page.
    """
    content = [b for b in doc.blocks if b.type != BlockType.PAGE_MARKER]
    if len(content) < 2:
        return 1.0

    good = 0
    total = 0
    for a, b in zip(content, content[1:]):
        total += 1
        if b.source_page < a.source_page:
            continue
        if b.source_page > a.source_page:
            good += 1
            continue
        ay = a.source_bounding_box.y1 if a.source_bounding_box else None
        by = b.source_bounding_box.y1 if b.source_bounding_box else None
        if ay is None or by is None or by <= ay + 1.0:
            good += 1

    return round(good / total, 3) if total else 1.0


def _table_structure_quality(table_struct) -> float:
    """Score an extracted table's structural soundness (TBL-001).

    Rewards rectangular row lengths, populated cells, and a detected header —
    a real property of the table rather than a comparison against itself.
    """
    rows = table_struct.rows
    if not rows:
        return 0.0

    col_count = table_struct.column_count or 1
    consistent = sum(1 for row in rows if len(row) == col_count)

    total_cells = 0
    populated = 0
    for row in rows:
        for cell in row:
            total_cells += 1
            if (cell.text or "").strip():
                populated += 1

    consistency = consistent / len(rows)
    fill = populated / total_cells if total_cells else 0.0
    header = 1.0 if table_struct.has_header else 0.5
    return round(0.4 * consistency + 0.4 * fill + 0.2 * header, 3)


def _page_anchor_fidelity(doc: DocumentIR) -> float:
    """Score whether every source page carries a page-anchor marker (PDF-006, OUT-005)."""
    pages = [p.page_number for p in doc.pages]
    if not pages:
        return 1.0
    markers = {b.page_marker for b in doc.blocks if b.type == BlockType.PAGE_MARKER}
    present = sum(1 for p in pages if p in markers)
    return round(present / len(pages), 3)


class BenchmarkCase(BaseModel):
    name: str
    file_path: str
    expected_page_count: int = 1
    expected_keywords: List[str] = Field(default_factory=list)
    has_table: bool = False
    expected_table_shape: Optional[tuple[int, int]] = None
    expected_image_count: int = 0


class BenchmarkResult(BaseModel):
    case_name: str
    format: str
    page_count: int
    duration_seconds: float
    metrics: EvaluationMetrics
    success: bool
    warning_count: int
    error_message: Optional[str] = None
    measurement_notes: List[str] = Field(default_factory=list)
    peak_vram_mb: float | None = None


class BenchmarkReport(BaseModel):
    """Machine-readable and human-readable benchmark summary (QA-002, PERF-002)."""

    timestamp: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    results: Dict[str, BenchmarkResult] = Field(default_factory=dict)
    average_cer: float | None = None
    average_wer: float | None = None
    average_speed_s_per_page: float = 0.0
    peak_ram_mb: float = 0.0

    def to_markdown_table(self) -> str:
        """Format benchmark results as a clean Markdown table (anti-slop, subject-grounded)."""
        lines = [
            "| Case Name | Format | Pages | CER | WER | Order heuristic | Table heuristic | Images | Anchors | Speed (s/p) | Process peak RAM (MB) | VRAM (MB) | Execution |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, r in self.results.items():
            status = "PASS" if r.success else "FAIL"
            m = r.metrics
            cer_label = f"{m.cer:.3f}" if m.cer is not None else "N/A"
            wer_label = f"{m.wer:.3f}" if m.wer is not None else "N/A"
            lines.append(
                f"| {name} | {r.format} | {r.page_count} | {cer_label} | {wer_label} | {m.reading_order_score:.2f} | {m.table_score:.2f} | {m.image_retention:.2f} | {m.page_anchor_fidelity:.2f} | {m.speed_sec_per_page:.2f} | {m.peak_ram_mb:.1f} | N/A | {status} |"
            )
        lines.append("\nPASS means conversion completed or malformed input was rejected safely. It is not a fidelity acceptance result. N/A means unmeasured. Order/table columns are heuristics; RAM excludes child processes and records the lifetime process peak.")
        return "\n".join(lines)


class BenchmarkRunner:
    """Orchestrates benchmark evaluation against the rights-safe corpus."""

    def __init__(self, corpus_dir: Optional[Path | str] = None):
        self.corpus_dir = (
            Path(corpus_dir)
            if corpus_dir
            else Path(tempfile.gettempdir()) / "olp_benchmark_corpus"
        )
        self.builder = BenchmarkCorpusBuilder(self.corpus_dir)
        self.orchestrator = PipelineOrchestrator()

    def run_benchmark(self, out_dir: Optional[Path | str] = None) -> BenchmarkReport:
        """Execute all benchmark cases and compile full metrics report."""
        cases = self.builder.build_all()
        target_out = Path(out_dir) if out_dir else self.corpus_dir / "outputs"
        target_out.mkdir(parents=True, exist_ok=True)

        results: Dict[str, BenchmarkResult] = {}
        total_cer = 0.0
        total_wer = 0.0
        total_speed = 0.0
        valid_cases_count = 0
        measured_text_cases = 0

        for name, file_path in cases.items():
            start_time = time.perf_counter()
            out_file = target_out / f"{name}_output.docx"

            # Check if this is the intentionally malformed case (14_malformed_pdf)
            if "malformed" in name:
                failure = None
                try:
                    self.orchestrator.convert(file_path, out_file)
                except Exception as error:
                    failure = type(error).__name__
                duration = time.perf_counter() - start_time
                results[name] = BenchmarkResult(
                    case_name=name,
                    format="pdf",
                    page_count=1,
                    duration_seconds=round(duration, 3),
                    metrics=EvaluationMetrics(
                        cer=None, wer=None, reading_order_score=0.0, table_score=0.0,
                        image_retention=0.0, page_anchor_fidelity=0.0,
                        speed_sec_per_page=round(duration, 3), peak_ram_mb=get_current_ram_mb(),
                    ),
                    success=failure is not None,
                    warning_count=1,
                    error_message=f"Safely caught: {failure}" if failure else "Malformed fixture was unexpectedly accepted.",
                    measurement_notes=["Rejection test; content fidelity metrics do not apply."],
                )
                continue

            try:
                res = self.orchestrator.convert(file_path, out_file)
                duration = time.perf_counter() - start_time
                doc_ir = res.document_ir
                page_count = max(1, len(doc_ir.pages))

                # Extract reconstructed text
                hyp_text = " ".join(" ".join(b.text.split()) for b in doc_ir.blocks if b.text and b.type != BlockType.PAGE_MARKER)

                gt_candidates = [
                    Path(str(file_path)).with_suffix(".txt"),
                    self.corpus_dir / "ocr_ground_truth" / f"{Path(str(file_path)).stem}.txt",
                ]
                ref_text = None
                for gt_path in gt_candidates:
                    try:
                        if gt_path.exists():
                            ref_text = gt_path.read_text(encoding="utf-8")
                            break
                    except Exception:
                        continue
                if ref_text is not None:
                    ref_text = " ".join(ref_text.split())
                    cer = calculate_cer(ref_text, hyp_text)
                    wer = calculate_wer(ref_text, hyp_text)
                else:
                    cer = None
                    wer = None

                # Reading order plausibility (detects scrambled order, not a self-comparison)
                reading_order_score = _reading_order_plausibility(doc_ir)

                # Table score: structural quality of any extracted table
                tables = [b for b in doc_ir.blocks if b.table_structure is not None]
                if "table" in name:
                    table_score = _table_structure_quality(tables[0].table_structure) if tables else 0.0
                else:
                    table_score = 1.0

                # Image retention: a case that should carry figures must retain them
                images = [b for b in doc_ir.blocks if b.image_asset is not None]
                if "images" in name or "mixed_digital_scan" in name:
                    image_retention = calculate_image_retention(1, len(images))
                else:
                    image_retention = 1.0

                # Page anchors: every source page must be traceable (PDF-006)
                anchor_fidelity = _page_anchor_fidelity(doc_ir)

                speed_per_page = duration / page_count

                # Memory usage
                max_rss_after = get_current_ram_mb()
                peak_ram = round(max_rss_after, 2)

                metrics = EvaluationMetrics(
                    cer=cer,
                    wer=wer,
                    reading_order_score=reading_order_score,
                    table_score=table_score,
                    image_retention=image_retention,
                    page_anchor_fidelity=anchor_fidelity,
                    speed_sec_per_page=round(speed_per_page, 3),
                    peak_ram_mb=max(0.0, peak_ram),
                )

                results[name] = BenchmarkResult(
                    case_name=name,
                    format=res.format,
                    page_count=page_count,
                    duration_seconds=round(duration, 3),
                    metrics=metrics,
                    success=True,
                    warning_count=len(res.warnings),
                    measurement_notes=[
                        "Reading order and table scores are heuristics, not ground-truth accuracy.",
                        "RAM is the process lifetime peak; child processes and VRAM are not measured.",
                        "Conversion success is not a document-fidelity pass.",
                    ] + (["No reference transcript: CER and WER unavailable."] if ref_text is None else []),
                )

                if cer is not None and wer is not None:
                    total_cer += cer
                    total_wer += wer
                    measured_text_cases += 1
                total_speed += speed_per_page
                valid_cases_count += 1

            except Exception as exc:
                duration = time.perf_counter() - start_time
                results[name] = BenchmarkResult(
                    case_name=name,
                    format="unknown",
                    page_count=1,
                    duration_seconds=round(duration, 3),
                    metrics=EvaluationMetrics(
                        cer=1.0,
                        wer=1.0,
                        reading_order_score=0.0,
                        table_score=0.0,
                        image_retention=0.0,
                        page_anchor_fidelity=0.0,
                        speed_sec_per_page=round(duration, 3),
                        peak_ram_mb=0.0,
                    ),
                    success=False,
                    warning_count=0,
                    error_message=str(exc),
                )

        passed = sum(1 for r in results.values() if r.success)
        avg_cer = round(total_cer / measured_text_cases, 4) if measured_text_cases else None
        avg_wer = round(total_wer / measured_text_cases, 4) if measured_text_cases else None
        avg_speed = round(total_speed / max(1, valid_cases_count), 3)

        report = BenchmarkReport(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            total_cases=len(cases),
            passed_cases=passed,
            failed_cases=len(cases) - passed,
            results=results,
            average_cer=avg_cer,
            average_wer=avg_wer,
            average_speed_s_per_page=avg_speed,
            peak_ram_mb=round(get_current_ram_mb(), 2),
        )

        return report
