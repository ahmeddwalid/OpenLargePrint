"""Tests for reflowed large-print PDF exporter (OUT-003, OUT-007..009)."""

from pathlib import Path
import pytest
import pypdfium2 as pdfium

from openlargeprint.exporters import ExportOptions, PaperSize, PdfExporter, PresetName
from openlargeprint.ir.models import (
    Block,
    BlockType,
    BoundingBox,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    PageClassification,
    PageMetadata,
)


def create_sample_ir() -> DocumentIR:
    metadata = DocumentMetadata(title="Jurisprudence and the Rule of Law", page_count=1)
    pages = [
        PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)
    ]
    blocks = [
        Block(id="p1_m", type=BlockType.PAGE_MARKER, source_page=1, page_marker=1),
        Block(
            id="p1_h1",
            type=BlockType.HEADING,
            text="Section A: The Inner Morality of Law",
            level=1,
            source_page=1,
        ),
        Block(
            id="p1_b1",
            type=BlockType.PARAGRAPH,
            text="Lon Fuller posited eight essential desiderata for a legal system to function justly.",
            source_page=1,
        ),
        Block(
            id="p1_fn",
            type=BlockType.FOOTNOTE,
            text="1. See Fuller, The Morality of Law (Yale University Press, 1964).",
            source_page=1,
        ),
    ]
    return DocumentIR(metadata=metadata, pages=pages, blocks=blocks)


def test_pdf_export_a4_dimensions(tmp_path: Path):
    """Verify large-print PDF exports with true A4 physical dimensions (OUT-003, OUT-007, OUT-009)."""
    doc_ir = create_sample_ir()
    out_pdf = tmp_path / "large_print_a4.pdf"

    exporter = PdfExporter()
    options = ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4)
    exporter.export(doc_ir, out_pdf, options)

    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0

    pdf = pdfium.PdfDocument(out_pdf)
    assert len(pdf) >= 1
    page = pdf[0]
    w, h = page.get_size()

    # A4 dimensions: 595.28 x 841.89 points (210 x 297 mm)
    assert pytest.approx(w, 1.0) == 595.28
    assert pytest.approx(h, 1.0) == 841.89

    # Verify text content and print reminder footer (OUT-009)
    tp = page.get_textpage()
    text = tp.get_text_range()
    assert "Inner Morality" in text
    assert "Print at 100% / actual size" in text
    assert "Original Page 1" in text


def test_pdf_export_a3_dimensions(tmp_path: Path):
    """Verify large-print PDF exports with true A3 physical dimensions (OUT-007, OUT-008)."""
    doc_ir = create_sample_ir()
    out_pdf = tmp_path / "large_print_a3.pdf"

    exporter = PdfExporter()
    options = ExportOptions(preset=PresetName.EXTRA_LARGE, paper_size=PaperSize.A3)
    exporter.export(doc_ir, out_pdf, options)

    pdf = pdfium.PdfDocument(out_pdf)
    w, h = pdf[0].get_size()

    # A3 dimensions: 841.89 x 1190.55 points (297 x 420 mm)
    assert pytest.approx(w, 1.0) == 841.89
    assert pytest.approx(h, 1.0) == 1190.55
