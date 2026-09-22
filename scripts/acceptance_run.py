"""End-to-end acceptance run over real documents (SPEC §2, SPEC §6, OUT-001..011).

Converts every PDF in --input-dir and reports what actually happened: source
pages, imported pages, pages that lost their anchor, output page geometry,
warnings, wall time, and peak process RAM.

Invariants checked per document:
  * conversion completes without an unhandled exception
  * no source page is silently dropped (every page keeps its anchor)
  * output geometry matches the requested paper size on every page

The report deliberately contains counts and metrics only. Document text is never
written to the report, the console, or the log (SEC-007), and the input
directory is never modified.

Usage:
    uv run python scripts/acceptance_run.py --max-pages 5     # smoke run
    uv run python scripts/acceptance_run.py --docx-too        # full run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pypdfium2 as pdfium                                            # noqa: E402
from reportlab.lib.pagesizes import A3, A4                            # noqa: E402

from openlargeprint.ir.models import BlockType                        # noqa: E402
from openlargeprint.pipeline import PipelineOrchestrator              # noqa: E402
from openlargeprint.qa.benchmark import get_current_ram_mb            # noqa: E402

PAPER = {"A4": A4, "A3": A3}


def source_page_count(path: Path) -> int:
    doc = pdfium.PdfDocument(str(path))
    try:
        return len(doc)
    finally:
        doc.close()


def output_page_sizes(path: Path) -> list[tuple[float, float]]:
    doc = pdfium.PdfDocument(str(path))
    try:
        return [tuple(doc[i].get_size()) for i in range(len(doc))]
    finally:
        doc.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "test-documents")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "scratch" / "acceptance")
    parser.add_argument("--paper-size", choices=sorted(PAPER), default="A4")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Convert only the first N pages of each document (smoke runs)")
    parser.add_argument("--docx-too", action="store_true",
                        help="Also produce a DOCX export for each document")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"Input directory not found: {args.input_dir}")
        return 2

    run_dir = args.out_dir / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    page_range = (1, args.max_pages) if args.max_pages else None
    expected_width, expected_height = PAPER[args.paper_size]

    documents = sorted(args.input_dir.glob("*.pdf"))
    if not documents:
        print(f"No PDF documents found in {args.input_dir}")
        return 2

    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for source in documents:
        started = time.perf_counter()
        row: dict[str, Any] = {"document": source.name}

        try:
            out_pdf = run_dir / f"{source.stem}_large.pdf"
            result = PipelineOrchestrator().convert(
                source, out_pdf, export_format="pdf", page_range=page_range
            )
            elapsed = time.perf_counter() - started

            total_source_pages = source_page_count(source)
            considered_pages = (
                min(total_source_pages, args.max_pages) if args.max_pages else total_source_pages
            )

            imported = len(result.document_ir.pages)
            marked = {
                b.page_marker
                for b in result.document_ir.blocks
                if b.type == BlockType.PAGE_MARKER
            }
            missing = sorted({p.page_number for p in result.document_ir.pages} - marked)

            sizes = output_page_sizes(out_pdf)
            wrong_geometry = [
                index + 1
                for index, (width, height) in enumerate(sizes)
                if abs(width - expected_width) > 1.0 or abs(height - expected_height) > 1.0
            ]

            row.update(
                {
                    "source_pages": total_source_pages,
                    "considered_pages": considered_pages,
                    "imported_pages": imported,
                    "pages_without_anchor": missing,
                    "output_pages": len(sizes),
                    "pages_with_wrong_geometry": wrong_geometry,
                    "warnings": len(result.warnings),
                    "seconds": round(elapsed, 2),
                    "seconds_per_page": round(elapsed / max(1, imported), 3),
                    "peak_ram_mb": round(get_current_ram_mb(), 1),
                    "output_mb": round(out_pdf.stat().st_size / 1048576, 2),
                }
            )

            if imported < considered_pages:
                failures.append(
                    f"{source.name}: imported {imported} of {considered_pages} pages"
                )
            if missing:
                failures.append(
                    f"{source.name}: {len(missing)} page(s) lost their anchor: {missing[:10]}"
                )
            if wrong_geometry:
                failures.append(
                    f"{source.name}: {len(wrong_geometry)} page(s) not {args.paper_size}"
                )

            if args.docx_too:
                out_docx = run_dir / f"{source.stem}_large.docx"
                PipelineOrchestrator().convert(
                    source, out_docx, export_format="docx", page_range=page_range
                )
                row["docx_mb"] = round(out_docx.stat().st_size / 1048576, 2)

        except Exception as error:  # noqa: BLE001 - the harness records every failure
            elapsed = time.perf_counter() - started
            row.update(
                {
                    "error": f"{type(error).__name__}: {error}",
                    "seconds": round(elapsed, 2),
                }
            )
            failures.append(f"{source.name}: conversion failed ({type(error).__name__})")

        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
        sys.stdout.flush()

    report = {
        "paper_size": args.paper_size,
        "max_pages": args.max_pages,
        "documents": len(rows),
        "failures": failures,
        "rows": rows,
    }
    (run_dir / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    header = [
        f"# Acceptance run {run_dir.name}",
        "",
        f"Paper size: {args.paper_size}. Max pages per document: {args.max_pages or 'all'}.",
        "",
        "| Document | Source pages | Imported | Pages without anchor | Output pages | Wrong geometry | Warnings | s/page | Peak RAM (MB) | Output (MB) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in rows:
        header.append(
            "| {doc} | {src} | {imp} | {anchors} | {out} | {geom} | {warn} | {spp} | {ram} | {mb} |".format(
                doc=item["document"],
                src=item.get("source_pages", "-"),
                imp=item.get("imported_pages", "-"),
                anchors=len(item.get("pages_without_anchor") or []),
                out=item.get("output_pages", "-"),
                geom=len(item.get("pages_with_wrong_geometry") or []),
                warn=item.get("warnings", "-"),
                spp=item.get("seconds_per_page", "-"),
                ram=item.get("peak_ram_mb", "-"),
                mb=item.get("output_mb", "-"),
            )
        )
    header += ["", f"Failures: {len(failures)}"]
    header += [f"- {failure}" for failure in failures]
    markdown = "\n".join(header) + "\n"
    (run_dir / "acceptance.md").write_text(markdown, encoding="utf-8")

    print()
    print(markdown)
    print(f"Report directory: {run_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
