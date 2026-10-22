#!/usr/bin/env python3
"""Convert test documents with a packaged engine (installed, portable or AppImage copy).

Runs the same checks as the packaging gate (native and scanned pages, A4 and A3,
PDF and Word, page selection, a non-ASCII file name) against the engine at the
given path, and also writes a Reader page.

    python packaging/smoke_convert.py <path to openlargeprint-sidecar>
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_packaging import PACKAGED_CONVERSION_TIMEOUT_SECONDS, verify_conversion  # noqa: E402


def reader_page(engine: Path) -> bool:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    with tempfile.TemporaryDirectory(prefix="olp-reader-") as directory:
        root = Path(directory)
        source = root / "reader source.pdf"
        pdf = canvas.Canvas(str(source), pagesize=A4)
        pdf.drawString(72, 700, "Reader smoke test paragraph.")
        pdf.save()
        output = root / "reader.html"
        command = {"command": "convert", "id": "smoke-reader", "file_path": str(source),
                   "output_path": str(output), "export_format": "reader", "paper_size": "A4"}
        subprocess.run([str(engine), "sidecar"], input=json.dumps(command) + "\n", capture_output=True,
                       text=True, encoding="utf-8", timeout=PACKAGED_CONVERSION_TIMEOUT_SECONDS, check=True)
        if not output.is_file():
            return False
        html = output.read_text("utf-8")
        return "Reader smoke test paragraph." in html and "Atkinson Hyperlegible" in html


def parallel_pages(engine: Path) -> bool:
    """Six pages with two page workers, with an Arabic font chosen: workers must start
    from the packaged engine (frozen processes) and keep the pages in order."""
    import os
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    with tempfile.TemporaryDirectory(prefix="olp-parallel-") as directory:
        root = Path(directory)
        source = root / "six pages.pdf"
        pdf = canvas.Canvas(str(source), pagesize=A4)
        for page in range(6):
            pdf.drawString(72, 700, f"Parallel page {page + 1} of the smoke test.")
            pdf.showPage()
        pdf.save()
        output = root / "six.html"
        command = {"command": "convert", "id": "smoke-parallel", "file_path": str(source),
                   "output_path": str(output), "export_format": "reader", "paper_size": "A4",
                   "latin_font": "lexend", "arabic_font": "amiri"}
        env = dict(os.environ, OLP_PAGE_WORKERS="2")
        subprocess.run([str(engine), "sidecar"], input=json.dumps(command) + "\n", capture_output=True,
                       text=True, encoding="utf-8", timeout=PACKAGED_CONVERSION_TIMEOUT_SECONDS, check=True,
                       env=env)
        if not output.is_file():
            return False
        html = output.read_text("utf-8")
        positions = [html.find(f"Parallel page {n} of") for n in range(1, 7)]
        return all(p >= 0 for p in positions) and positions == sorted(positions) and '"Lexend"' in html


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    engine = Path(sys.argv[1]).resolve()
    if not engine.is_file():
        print(f"error: engine not found at {engine}")
        return 1
    if not verify_conversion(engine):
        print("error: the packaged engine did not convert the test documents correctly")
        return 1
    if not reader_page(engine):
        print("error: the packaged engine did not write a Reader page")
        return 1
    if not parallel_pages(engine):
        print("error: the packaged engine did not convert pages in parallel workers")
        return 1
    print(f"ok: {engine} converted native and scanned pages to PDF, Word and Reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
