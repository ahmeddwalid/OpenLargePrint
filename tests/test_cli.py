"""Tests for standalone CLI commands (DESIGN.md §1, UI-001, UI-005)."""

import json
from pathlib import Path
import subprocess
import sys
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

CLI_CMD = [sys.executable, "-m", "openlargeprint.cli"]


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

    cmd = CLI_CMD + [
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

    cmd = CLI_CMD + ["inspect", str(input_pdf)]
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

    cmd = CLI_CMD + ["inspect", str(input_pdf), "--json"]
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

    cmd = CLI_CMD + ["convert", str(fake_file), "-o", str(tmp_path / "out.docx")]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
    assert "Error: File format not recognized" in res.stderr


def test_sidecar_accepts_utf8_paths_with_windows_code_page(tmp_path: Path):
    import os

    source = tmp_path / "قراءة.pdf"
    create_minimal_pdf(source)
    payload = json.dumps({"command": "inspect", "file_path": str(source)}, ensure_ascii=False)
    result = subprocess.run(
        CLI_CMD + ["sidecar"], input=(payload + "\n").encode("utf-8"),
        capture_output=True, timeout=30,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
    )
    assert result.returncode == 0
    event = json.loads(result.stdout.decode("utf-8"))
    assert event["type"] == "inspect_result"
    assert event["file_name"] == source.name

def test_cli_benchmark_gate_passes_on_the_default_corpus(tmp_path: Path):
    """The benchmark must be runnable as a release gate (QA-001)."""
    cmd = CLI_CMD + [
        "benchmark",
        "--corpus-dir", str(tmp_path / "corpus"),
        "--out-dir", str(tmp_path / "out"),
        "--fail-on-mismatch",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "| Case Name |" in result.stdout
    assert "Expectation mismatches" not in result.stdout
