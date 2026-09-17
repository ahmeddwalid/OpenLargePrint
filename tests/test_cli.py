"""Tests for standalone CLI commands (DESIGN.md §1, UI-001, UI-005)."""

import json
from pathlib import Path
import subprocess
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_minimal_pdf(pdf_path: Path):
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 700, "Legal Memorandum")
    c.setFont("Helvetica", 12)
    c.drawString(50, 660, "This is a memorandum regarding statutory construction.")
    c.showPage()
    c.save()


def test_cli_convert(tmp_path: Path):
    """Verify CLI convert command produces a valid DOCX."""
    input_pdf = tmp_path / "memo.pdf"
    output_docx = tmp_path / "memo_large.docx"
    create_minimal_pdf(input_pdf)

    cmd = [
        ".venv/bin/openlargeprint",
        "convert",
        str(input_pdf),
        "-o",
        str(output_docx),
        "--preset",
        "Large",
        "--paper-size",
        "A4",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Successfully converted" in res.stdout
    assert "20.0pt" in res.stdout
    assert output_docx.exists()
    assert output_docx.stat().st_size > 0


def test_cli_inspect_text(tmp_path: Path):
    """Verify CLI inspect command prints page diagnostics without leaking text."""
    input_pdf = tmp_path / "memo.pdf"
    create_minimal_pdf(input_pdf)

    cmd = [".venv/bin/openlargeprint", "inspect", str(input_pdf)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Page classifications:" in res.stdout
    assert "Page 1: native" in res.stdout
    # Ensure document content itself is not dumped in stdout (SEC-007)
    assert "statutory construction" not in res.stdout


def test_cli_inspect_json(tmp_path: Path):
    """Verify CLI inspect --json outputs valid DocumentIR JSON."""
    input_pdf = tmp_path / "memo.pdf"
    create_minimal_pdf(input_pdf)

    cmd = [".venv/bin/openlargeprint", "inspect", str(input_pdf), "--json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["schema_version"] == "1.0.0"
    assert data["metadata"]["page_count"] == 1
    assert len(data["blocks"]) > 0


def test_cli_handles_invalid_file(tmp_path: Path):
    """Verify CLI prints user-friendly error on invalid file (UI-005)."""
    fake_file = tmp_path / "not_a_pdf.pdf"
    fake_file.write_text("just text")

    cmd = [".venv/bin/openlargeprint", "convert", str(fake_file), "-o", str(tmp_path / "out.docx")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Error: File format not recognized" in res.stderr
