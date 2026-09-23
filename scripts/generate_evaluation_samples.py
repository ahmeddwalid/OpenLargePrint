"""Generate evaluation samples across all formats for documents in test-documents (SPEC §3, OUT-001..011).

Saves converted outputs directly into:
    test-documents/outputs/<document_name>/
      ├── large_print_A4.pdf
      ├── large_print_A3.pdf
      ├── large_print.docx
      ├── reader_view.html
      └── searchable_original.pdf
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from openlargeprint.exporters import (
    DocxExporter,
    ExportOptions,
    PaperSize,
    PdfExporter,
    PresetName,
    ReaderExporter,
    SearchablePdfExporter,
)
from openlargeprint.pipeline import PipelineOrchestrator
from openlargeprint.security.isolation import JobWorkspace


def safe_dirname(name: str) -> str:
    base = Path(name).stem
    cleaned = re.sub(r"[^\w\-\.]+", "_", base).strip("_")
    return cleaned[:60]


def parse_page_range(spec: str) -> Optional[Set[int]]:
    """Parse a page specification like '1-10', '1..20', 'all', or '1,2,5'."""
    if not spec or spec.lower() in ("all", "full"):
        return None
    pages: Set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.update(range(int(start), int(end) + 1))
        elif ".." in part:
            start, end = part.split("..", 1)
            pages.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            pages.add(int(part))
    return pages if pages else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate evaluation samples for test documents.")
    parser.add_argument("--docs", type=str, default="", help="Filter documents by substring")
    parser.add_argument("--pages", type=str, default="1-15", help="Page range to convert (e.g. '1-20', '1-50', or 'all')")
    parser.add_argument("--full", action="store_true", help="Process entirety of each document (overrides --pages)")
    parser.add_argument("--format", type=str, default="all", help="Output format: 'all', 'pdf', 'docx', 'reader', or 'searchable'")
    args = parser.parse_args()

    input_dir = REPO_ROOT / "test-documents"
    output_root = input_dir / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)

    all_pdfs = sorted([f for f in input_dir.glob("*.pdf") if f.is_file()])
    if args.docs:
        query = args.docs.lower()
        pdf_files = [f for f in all_pdfs if query in f.name.lower()]
    else:
        pdf_files = all_pdfs

    if not pdf_files:
        print(f"No matching PDF files found in {input_dir}")
        return 1

    selected_pages = None if args.full else parse_page_range(args.pages)
    range_str = "full book (all pages)" if selected_pages is None else f"pages {min(selected_pages)}-{max(selected_pages)} ({len(selected_pages)} pages)"

    print(f"============================================================")
    print(f"OpenLargePrint — Evaluation Output Generation")
    print(f"Target documents: {len(pdf_files)}")
    print(f"Scope:            {range_str}")
    print(f"Formats:          {args.format}")
    print(f"Destination:      {output_root}")
    print(f"============================================================\n")

    orchestrator = PipelineOrchestrator()
    summary_rows = []

    for idx, doc in enumerate(pdf_files, 1):
        folder_name = safe_dirname(doc.name)
        target_dir = output_root / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{idx}/{len(pdf_files)}] Processing: {doc.name}")
        started = time.perf_counter()

        # Step 1: Import once into canonical DocumentIR (SPEC §2 Principle 2)
        print("   -> Importing into DocumentIR...", end="", flush=True)
        t_import = time.perf_counter()
        with JobWorkspace() as ws:
            doc_ir = orchestrator.pdf_importer.import_document(
                doc,
                ws,
                selected_pages=selected_pages,
            )
            print(f" done ({len(doc_ir.blocks)} blocks in {round(time.perf_counter() - t_import, 2)}s)")

            opts_a4 = ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4)
            opts_a3 = ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A3)

            a4_pdf_kb = 0.0
            a3_pdf_kb = 0.0
            docx_kb = 0.0
            reader_kb = 0.0
            searchable_kb = 0.0

            # Step 2: Multi-format exports without re-importing (OUT-002)
            if args.format in ("all", "pdf"):
                pdf_a4_path = target_dir / "large_print_A4.pdf"
                PdfExporter().export(doc_ir, pdf_a4_path, opts_a4)
                a4_pdf_kb = round(pdf_a4_path.stat().st_size / 1024, 1)
                print(f"   -> A4 PDF:       {pdf_a4_path.name} ({a4_pdf_kb} KB)")

                pdf_a3_path = target_dir / "large_print_A3.pdf"
                PdfExporter().export(doc_ir, pdf_a3_path, opts_a3)
                a3_pdf_kb = round(pdf_a3_path.stat().st_size / 1024, 1)
                print(f"   -> A3 PDF:       {pdf_a3_path.name} ({a3_pdf_kb} KB)")

            if args.format in ("all", "docx"):
                docx_path = target_dir / "large_print.docx"
                DocxExporter().export(doc_ir, docx_path, opts_a4)
                docx_kb = round(docx_path.stat().st_size / 1024, 1)
                print(f"   -> DOCX:         {docx_path.name} ({docx_kb} KB)")

            if args.format in ("all", "reader"):
                reader_path = target_dir / "reader_view.html"
                ReaderExporter().export(doc_ir, reader_path, opts_a4)
                reader_kb = round(reader_path.stat().st_size / 1024, 1)
                print(f"   -> Reader HTML:  {reader_path.name} ({reader_kb} KB)")

            if args.format in ("all", "searchable"):
                searchable_path = target_dir / "searchable_original.pdf"
                SearchablePdfExporter().export(
                    doc,
                    searchable_path,
                    ocr_engine=orchestrator.pdf_importer.ocr_engine,
                    selected_pages=selected_pages,
                )
                searchable_kb = round(searchable_path.stat().st_size / 1024, 1)
                print(f"   -> Searchable:   {searchable_path.name} ({searchable_kb} KB)")

        elapsed = round(time.perf_counter() - started, 2)
        print(f"   Completed in {elapsed}s\n")

        summary_rows.append(
            {
                "original": doc.name,
                "folder": folder_name,
                "pages": range_str,
                "blocks": len(doc_ir.blocks),
                "a4_pdf_kb": a4_pdf_kb,
                "a3_pdf_kb": a3_pdf_kb,
                "docx_kb": docx_kb,
                "reader_kb": reader_kb,
                "searchable_kb": searchable_kb,
                "elapsed": elapsed,
            }
        )

    # Write summary index
    summary_md = output_root / "summary.md"
    lines = [
        "# OpenLargePrint — Evaluation Outputs",
        "",
        f"Generated samples across {len(pdf_files)} test documents.",
        f"**Scope**: {range_str}",
        "",
        "| Document | Blocks | Large A4 PDF | Large A3 PDF | DOCX | Reader HTML | Searchable PDF | Time (s) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in summary_rows:
        f = row["folder"]
        lines.append(
            f"| **{row['original']}** | {row['blocks']} | [{row['a4_pdf_kb']} KB]({f}/large_print_A4.pdf) | [{row['a3_pdf_kb']} KB]({f}/large_print_A3.pdf) | [{row['docx_kb']} KB]({f}/large_print.docx) | [{row['reader_kb']} KB]({f}/reader_view.html) | [{row['searchable_kb']} KB]({f}/searchable_original.pdf) | {row['elapsed']} |"
        )
    lines.append("")
    summary_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"All outputs saved to: {output_root}")
    print(f"Summary generated at: {summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
