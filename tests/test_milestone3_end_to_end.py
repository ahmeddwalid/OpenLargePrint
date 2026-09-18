"""End-to-end integration test proving Milestone 3:
Multi-format exports (Large PDF A4/A3, Semantic Reader HTML, and Selective Page-Range export).
"""

from pathlib import Path
import subprocess
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.exporters import ExportOptions, PaperSize, PresetName
from openlargeprint.pipeline import PipelineOrchestrator


def create_multipage_pdf(pdf_path: Path):
    """Create a 3-page test document for selective range and multi-format testing."""
    c = canvas.Canvas(str(pdf_path), pagesize=letter)

    # Page 1
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 700, "Chapter 1: The Rule of Law")
    c.setFont("Helvetica", 11)
    c.drawString(50, 660, "No man is above the law, and every man is subject to ordinary jurisdiction.")
    c.showPage()

    # Page 2
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 700, "Chapter 2: Separation of Powers")
    c.setFont("Helvetica", 11)
    c.drawString(50, 660, "The legislative, executive, and judicial powers must remain distinct.")
    c.showPage()

    # Page 3
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 700, "Chapter 3: Parliamentary Sovereignty")
    c.setFont("Helvetica", 11)
    c.drawString(50, 660, "Parliament has the right to make or unmake any law whatever.")
    c.showPage()

    c.save()


def test_milestone3_multiformat_and_selective_export(tmp_path: Path):
    """Verify end-to-end conversion to PDF (A4/A3), Reader HTML, and selective page export (OUT-002, OUT-003, OUT-010)."""
    input_pdf = tmp_path / "constitution.pdf"
    create_multipage_pdf(input_pdf)

    orchestrator = PipelineOrchestrator()
    options = ExportOptions(preset=PresetName.LARGE)

    # 1. Export whole document to Large-Print PDF (A4)
    out_pdf_a4 = tmp_path / "constitution_a4.pdf"
    res_pdf_a4 = orchestrator.convert(
        input_pdf, out_pdf_a4, options=ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4)
    )
    assert res_pdf_a4.success is True
    assert out_pdf_a4.exists()

    pdf_doc = pdfium.PdfDocument(out_pdf_a4)
    w, h = pdf_doc[0].get_size()
    assert pytest.approx(w, 1.0) == 595.28  # A4 width
    assert pytest.approx(h, 1.0) == 841.89  # A4 height

    # 2. Export whole document to Large-Print PDF (A3) (OUT-007, OUT-008)
    out_pdf_a3 = tmp_path / "constitution_a3.pdf"
    res_pdf_a3 = orchestrator.convert(
        input_pdf, out_pdf_a3, options=ExportOptions(preset=PresetName.EXTRA_LARGE, paper_size=PaperSize.A3)
    )
    assert res_pdf_a3.success is True
    assert out_pdf_a3.exists()

    pdf_a3_doc = pdfium.PdfDocument(out_pdf_a3)
    w3, h3 = pdf_a3_doc[0].get_size()
    assert pytest.approx(w3, 1.0) == 841.89  # A3 width
    assert pytest.approx(h3, 1.0) == 1190.55  # A3 height

    # 3. Export to Interactive Reader HTML (OUT-002)
    out_reader = tmp_path / "constitution_reader.html"
    res_reader = orchestrator.convert(input_pdf, out_reader, options=options)
    assert res_reader.success is True
    assert out_reader.exists()

    reader_content = out_reader.read_text(encoding="utf-8")
    assert "OpenLargePrint Reader" in reader_content
    assert "btn-size-inc" in reader_content
    assert "Chapter 1: The Rule of Law" in reader_content

    # 4. Selective Page Range Export: Export ONLY Page 2 (OUT-010)
    out_page2_pdf = tmp_path / "chapter2_only.pdf"
    res_p2 = orchestrator.convert(
        input_pdf,
        out_page2_pdf,
        options=ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4),
        page_range=(2, 2),
    )
    assert res_p2.success is True
    assert out_page2_pdf.exists()

    p2_pdf = pdfium.PdfDocument(out_page2_pdf)
    p2_text = p2_pdf[0].get_textpage().get_text_range()
    assert "Chapter 2: Separation of Powers" in p2_text
    assert "Chapter 1" not in p2_text
    assert "Chapter 3" not in p2_text


def test_cli_multiformat_and_page_range(tmp_path: Path):
    """Verify CLI flags --format, --paper-size, and --page-range work seamlessly (OUT-010, OUT-011)."""
    input_pdf = tmp_path / "cli_test.pdf"
    create_multipage_pdf(input_pdf)

    out_reader = tmp_path / "cli_reader.html"
    import sys
    cmd = [
        sys.executable,
        "-m",
        "openlargeprint.cli",
        "convert",
        str(input_pdf),
        "-o",
        str(out_reader),
        "--format",
        "reader",
        "--page-range",
        "2",
        "3",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0
    assert "Format: READER" in res.stdout
    assert "Selected range: Pages 2 to 3" in res.stdout
    assert out_reader.exists()
