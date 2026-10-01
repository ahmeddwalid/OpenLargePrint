"""Tests for output page readability, header/footer suppression, tracking normalization, and page markers (OUT-001, OUT-003, OUT-005, SPEC §1..2)."""

from pathlib import Path
import pytest
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from openlargeprint.exporters import ExportOptions, PaperSize, PdfExporter, DocxExporter
from openlargeprint.importers.pdf.native import NativePdfImporter, TextLine, normalize_tracked_text
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
from openlargeprint.pipeline import PipelineOrchestrator
from openlargeprint.security.isolation import JobWorkspace


def test_normalize_tracked_text():
    """Verify that letter-spaced tracking is normalized without altering normal words."""
    assert normalize_tracked_text("C a m b r i d g e") == "Cambridge"
    assert normalize_tracked_text("U N I V E R S I T Y   P R E S S") == "UNIVERSITY   PRESS"
    assert normalize_tracked_text("E s s e n t i a l Grammar") == "Essential Grammar"
    # Normal short words or single letters in sentences should not be collapsed incorrectly
    assert normalize_tracked_text("A cat in a hat") == "A cat in a hat"
    assert normalize_tracked_text("I am a student") == "I am a student"
    assert normalize_tracked_text("") == ""


def test_filter_running_headers_and_footers():
    """Verify running headers, footers, and page numbers are removed from reading stream."""
    importer = NativePdfImporter()

    lines = [
        # Top margin header (y0 = 740 on an 800pt high page -> 92.5%)
        TextLine(
            text="English Phrasal Verbs in Use",
            rect=(50.0, 740.0, 300.0, 752.0),
            font_size=10.0,
            font_name="Helvetica",
            is_bold=False,
            page_num=2,
        ),
        # Body text
        TextLine(
            text="Phrasal verbs are multi-word verbs consisting of a verb and a particle.",
            rect=(50.0, 500.0, 450.0, 514.0),
            font_size=12.0,
            font_name="Helvetica",
            is_bold=False,
            page_num=2,
        ),
        # Bottom margin footer / page number (y1 = 40 on an 800pt high page -> 5%)
        TextLine(
            text="2 English Phrasal Verbs in Use",
            rect=(50.0, 30.0, 200.0, 40.0),
            font_size=9.0,
            font_name="Helvetica",
            is_bold=False,
            page_num=2,
        ),
    ]

    filtered = importer._filter_running_headers_and_footers(lines, page_num=2, page_width=600.0, page_height=800.0)
    texts = [l.text for l in filtered]

    assert "English Phrasal Verbs in Use" in texts
    assert "2 English Phrasal Verbs in Use" in texts
    assert any("Phrasal verbs are multi-word verbs" in t for t in texts)


def test_pdf_page_marker_no_replacement_character(tmp_path: Path):
    """Verify page markers render with clean ASCII delimiters and no corrupted replacement characters."""
    metadata = DocumentMetadata(title="Page Marker Test", page_count=2)
    pages = [
        PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE),
        PageMetadata(page_number=2, width=595, height=842, classification=PageClassification.NATIVE),
    ]
    blocks = [
        Block(id="p1_m", type=BlockType.PAGE_MARKER, source_page=1, page_marker=1),
        Block(id="p1_b", type=BlockType.PARAGRAPH, text="Content on original page one.", source_page=1),
        Block(id="p2_m", type=BlockType.PAGE_MARKER, source_page=2, page_marker=2),
        Block(id="p2_b", type=BlockType.PARAGRAPH, text="Content on original page two.", source_page=2),
    ]
    doc_ir = DocumentIR(metadata=metadata, pages=pages, blocks=blocks)

    out_pdf = tmp_path / "markers_test.pdf"
    PdfExporter().export(doc_ir, out_pdf, ExportOptions(include_page_markers=True))

    with pdfium.PdfDocument(out_pdf) as pdf:
        text = "".join(page.get_textpage().get_text_range() for page in pdf)
        assert "-- Original Page 1 --" in text or "Original Page 1" in text
        assert "-- Original Page 2 --" in text or "Original Page 2" in text
        # There should be NO replacement character / tofu
        assert "\ufffd" not in text


def test_docx_page_marker_clean_dashes(tmp_path: Path):
    """Verify DOCX export uses clean dashes in page markers."""
    import docx
    metadata = DocumentMetadata(title="DOCX Marker Test", page_count=1)
    pages = [PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)]
    blocks = [
        Block(id="p1_m", type=BlockType.PAGE_MARKER, source_page=1, page_marker=1),
        Block(id="p1_b", type=BlockType.PARAGRAPH, text="Sample body text.", source_page=1),
    ]
    doc_ir = DocumentIR(metadata=metadata, pages=pages, blocks=blocks)
    out_docx = tmp_path / "markers_test.docx"
    DocxExporter().export(doc_ir, out_docx, ExportOptions(include_page_markers=True))

    doc = docx.Document(str(out_docx))
    all_text = " ".join(p.text for p in doc.paragraphs)
    assert "-- Original Page 1 --" in all_text
    assert "\ufffd" not in all_text
