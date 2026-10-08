"""Convert sample pages from local books and render the results for inspection.

    python scripts/review_pages.py test-documents --pages 1,15,41 --out scratch/review

For each PDF the selected pages are converted to a large-print PDF (and, with
``--docx``, a Word file). Every output page is rendered to PNG next to a
render of the matching source page, so the two can be compared side by side.
A short summary of block types and warnings is written to ``summary.json``;
it contains no document text.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pypdfium2 as pdfium  # noqa: E402

from openlargeprint.exporters import ExportOptions  # noqa: E402
from openlargeprint.exporters.base import PaperSize, PresetName  # noqa: E402
from openlargeprint.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402


def render(pdf_path: Path, out_dir: Path, prefix: str, pages=None, scale: float = 0.75) -> int:
    doc = pdfium.PdfDocument(str(pdf_path))
    count = 0
    for index in range(len(doc)):
        if pages is not None and index + 1 not in pages:
            continue
        doc[index].render(scale=scale).to_pil().save(out_dir / f"{prefix}{index + 1:03d}.png")
        count += 1
    doc.close()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="A PDF or a folder of PDFs")
    parser.add_argument("--pages", default="1,15,41", help="Source pages to convert, e.g. 1,15,41-42")
    parser.add_argument("--out", type=Path, default=ROOT / "scratch" / "review")
    parser.add_argument("--size", default="Large", choices=[p.value for p in PresetName if p != PresetName.CUSTOM])
    parser.add_argument("--paper", default="A4", choices=["A4", "A3"])
    parser.add_argument("--docx", action="store_true", help="Also write a Word file")
    args = parser.parse_args()

    books = sorted(args.source.glob("*.pdf")) if args.source.is_dir() else [args.source]
    orchestrator = PipelineOrchestrator()
    summary = {}
    for book in books:
        name = "".join(c if c.isalnum() else "_" for c in book.stem)[:40].strip("_")
        out_dir = args.out / name
        out_dir.mkdir(parents=True, exist_ok=True)
        with pdfium.PdfDocument(str(book)) as probe:
            total = len(probe)
        wanted = set()
        for part in args.pages.split(","):
            lo, _, hi = part.partition("-")
            for n in range(int(lo), int(hi or lo) + 1):
                if 1 <= n <= total:
                    wanted.add(n)
        options = ExportOptions(preset=PresetName(args.size), paper_size=PaperSize(args.paper))
        started = time.perf_counter()
        result = orchestrator.convert(book, out_dir / "large_print.pdf", options=options,
                                      export_format="pdf", page_range=sorted(wanted))
        elapsed = time.perf_counter() - started
        if args.docx:
            orchestrator.convert(book, out_dir / "large_print.docx", options=options,
                                 export_format="docx", page_range=sorted(wanted))
        output_pages = render(out_dir / "large_print.pdf", out_dir, "out_")
        render(book, out_dir, "src_", pages=wanted, scale=0.6)
        ir = result.document_ir
        summary[name] = {
            "source_pages": sorted(wanted),
            "output_pages": output_pages,
            "seconds": round(elapsed, 1),
            "seconds_per_page": round(elapsed / max(1, len(wanted)), 2),
            "blocks": dict(Counter(b.type.value for b in ir.blocks)),
            "flagged_blocks": sum(1 for b in ir.blocks if b.warnings),
            "classifications": dict(Counter(p.classification.value for p in ir.pages)),
        }
        print(f"{name}: {len(wanted)} pages -> {output_pages} pages in {elapsed:.1f}s")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
