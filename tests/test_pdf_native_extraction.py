"""Tests for native PDF text extraction, column ordering, and provenance (PDF-002, PDF-006, OUT-005)."""

from pathlib import Path
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import BlockType, ExtractionMethod
from openlargeprint.security.isolation import JobWorkspace


def create_two_column_pdf(pdf_path: Path):
    """Generate a born-digital two-column legal text page."""
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    
    # Full-width main heading
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, 720, "Title: The Doctrine of Judicial Precedent")

    # Column 1 (left: x=50, width~220)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 680, "Section 1: Common Law Roots")
    c.setFont("Helvetica", 10)
    c.drawString(50, 660, "First paragraph of column one.")
    c.drawString(50, 645, "Second line of column one paragraph.")
    c.drawString(50, 610, "Another paragraph in column one.")

    # Column 2 (right: x=320, width~220)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(320, 680, "Section 2: Stare Decisis Application")
    c.setFont("Helvetica", 10)
    c.drawString(320, 660, "First paragraph of column two.")
    c.drawString(320, 645, "Second line of column two paragraph.")
    c.drawString(320, 610, "Another paragraph in column two.")

    c.showPage()
    c.save()


def test_native_extraction_two_column_reading_order(tmp_path: Path):
    """Verify that a two-column page is read column-by-column rather than interleaved horizontally."""
    pdf_path = tmp_path / "two_column.pdf"
    create_two_column_pdf(pdf_path)

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc = importer.import_document(pdf_path, ws)

    assert doc.metadata.page_count == 1
    assert len(doc.blocks) > 0

    # First block is the page marker (OUT-005)
    assert doc.blocks[0].type == BlockType.PAGE_MARKER
    assert doc.blocks[0].page_marker == 1

    # Extract text contents of semantic blocks
    content_blocks = [b for b in doc.blocks if b.type != BlockType.PAGE_MARKER]
    texts = [b.text for b in content_blocks]

    # Verify Title is first
    assert "Title: The Doctrine of Judicial Precedent" in texts[0]
    assert content_blocks[0].type == BlockType.HEADING
    assert content_blocks[0].level == 1

    # Verify Section 1 (Column 1) comes before Section 2 (Column 2)
    sec1_idx = next(i for i, t in enumerate(texts) if "Section 1" in t)
    col1_body_idx = next(i for i, t in enumerate(texts) if "First paragraph of column one" in t)
    sec2_idx = next(i for i, t in enumerate(texts) if "Section 2" in t)
    col2_body_idx = next(i for i, t in enumerate(texts) if "First paragraph of column two" in t)

    assert sec1_idx < col1_body_idx, "Heading 1 should precede Column 1 text"
    assert col1_body_idx < sec2_idx, "All Column 1 content must precede Column 2 heading"
    assert sec2_idx < col2_body_idx, "Column 2 heading must precede Column 2 text"


def test_provenance_and_bounding_boxes(tmp_path: Path):
    """Verify that every extracted block carries source_page and source_bounding_box (PDF-006)."""
    pdf_path = tmp_path / "provenance.pdf"
    create_two_column_pdf(pdf_path)

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc = importer.import_document(pdf_path, ws)

    for block in doc.blocks:
        assert block.source_page == 1
        assert block.extraction_method == ExtractionMethod.NATIVE
        if block.type != BlockType.PAGE_MARKER:
            assert block.source_bounding_box is not None
            bbox = block.source_bounding_box
            assert bbox.width > 0
            assert bbox.height > 0
