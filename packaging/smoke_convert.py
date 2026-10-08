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
    print(f"ok: {engine} converted native and scanned pages to PDF, Word and Reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
