"""Tests for scanned PDF layout recognition, coordinate translation, and reading order (PDF-003, PDF-006, OCR-004, OCR-005)."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.classifier import classify_pdf_page
from openlargeprint.importers.pdf.scanned import ScannedPageExtractor
from openlargeprint.ir.models import BlockType, ExtractionMethod, PageClassification
from openlargeprint.ocr.paddle_engine import PaddleRapidOcrEngine
from openlargeprint.security.isolation import JobWorkspace
import pypdfium2 as pdfium


def generate_scanned_two_column_pdf(pdf_path: Path, img_path: Path):
    """Generate a pure image scanned PDF: text rendered into bitmap raster with no text layer."""
    # Create 200 DPI image for letter page (8.5 x 11 in -> 1700 x 2200 px)
    w_px, h_px = 1700, 2200
    img = Image.new("RGB", (w_px, h_px), color="white")
    draw = ImageDraw.Draw(img)

    # Use default font or scaled font
    # Draw Chapter heading across top
    draw.text((150, 150), "Chapter 7: Commercial Contracts and Remedies", fill="black")

    # Column 1 (x: 150 to 800)
    draw.text((150, 300), "1. Anticipatory Breach Doctrine", fill="black")
    draw.text((150, 400), "Repudiation prior to agreed performance allows immediate action.", fill="black")
    draw.text((150, 480), "The innocent party may elect to accept repudiation or affirm.", fill="black")
    draw.text((150, 560), "Election once communicated to the breaching party is irrevocable.", fill="black")

    # Column 2 (x: 950 to 1600)
    draw.text((950, 300), "2. Liquidated Damages and Penalties", fill="black")
    draw.text((950, 400), "Clauses must represent a genuine pre-estimate of loss incurred.", fill="black")
    draw.text((950, 480), "Extravagant and unconscionable sums are unenforceable penalties.", fill="black")
    draw.text((950, 560), "The modern test assesses legitimate commercial interests protected.", fill="black")

    img.save(img_path)

    # Embed as full page image on PDF
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawImage(str(img_path), 0, 0, width=letter[0], height=letter[1])
    c.showPage()
    c.save()


def test_scanned_page_classification(tmp_path: Path):
    """Verify that pure raster scan is classified as SCANNED (PDF-001)."""
    pdf_path = tmp_path / "scan_test.pdf"
    img_path = tmp_path / "scan_test.png"
    generate_scanned_two_column_pdf(pdf_path, img_path)

    pdf = pdfium.PdfDocument(pdf_path)
    page_meta = classify_pdf_page(pdf[0], 1)
    assert page_meta.classification == PageClassification.SCANNED
    assert page_meta.details["char_count"] == 0
    assert page_meta.details["raster_coverage"] >= 0.85


def test_scanned_page_extraction_and_column_ordering(tmp_path: Path):
    """Verify ScannedPageExtractor renders, runs OCR, reconstructs columns, and sets bounding boxes (PDF-003, PDF-006)."""
    pdf_path = tmp_path / "scan_order.pdf"
    img_path = tmp_path / "scan_order.png"
    generate_scanned_two_column_pdf(pdf_path, img_path)

    engine = PaddleRapidOcrEngine()
    extractor = ScannedPageExtractor(ocr_engine=engine, dpi=200.0)

    pdf = pdfium.PdfDocument(pdf_path)
    blocks = extractor.extract_page(pdf[0], page_num=1, start_block_idx=1)

    assert len(blocks) > 0

    # Verify all blocks have extraction_method = OCR_FAST and valid bounding box in PDF points (PDF-006)
    for block in blocks:
        assert block.extraction_method == ExtractionMethod.OCR_FAST
        assert block.confidence > 0.60
        assert block.source_bounding_box is not None
        bbox = block.source_bounding_box
        assert bbox.x0 >= 0 and bbox.x1 <= letter[0] + 10
        assert bbox.y0 >= 0 and bbox.y1 <= letter[1] + 10
        assert bbox.width > 0
        assert bbox.height > 0

    # Verify Column 1 text precedes Column 2 text (PDF-003)
    texts = [b.text for b in blocks if b.text]
    full_text = " ".join(texts)

    assert "Commercial Contracts" in full_text
    sec1_idx = next(i for i, t in enumerate(texts) if "Anticipatory Breach" in t or "Repudiation" in t)
    sec2_idx = next(i for i, t in enumerate(texts) if "Liquidated Damages" in t or "Penalties" in t)
    assert sec1_idx < sec2_idx, "Column 1 text must precede Column 2 text in reading order"
