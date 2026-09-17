"""Tests for broken-digital page detection and OCR fallback (PDF-005)."""

from pathlib import Path
from PIL import Image, ImageDraw
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.classifier import classify_pdf_page
from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import ExtractionMethod, PageClassification
from openlargeprint.security.isolation import JobWorkspace
import pypdfium2 as pdfium


def create_broken_digital_pdf(pdf_path: Path, img_path: Path):
    """Generate a PDF with a legible background image but corrupted/replacement text layer."""
    # 1. Background image with legible text
    img = Image.new("RGB", (1200, 400), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((50, 80), "Doctrine of Promissory Estoppel", fill="black")
    draw.text((50, 160), "Equity intervenes where unconscionable reliance occurs.", fill="black")
    img.save(img_path)

    # 2. PDF drawing image, but with broken/garbled text layer (e.g. font encoding corruption)
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawImage(str(img_path), 50, 450, width=500, height=200)

    # Add garbled unicode replacement text layer
    garbled_text = "\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd"
    for y in range(600, 450, -30):
        c.drawString(50, y, garbled_text)
    c.showPage()
    c.save()


def test_classifier_detects_broken_digital(tmp_path: Path):
    """Verify that a page dominated by replacement characters is classified as BROKEN_DIGITAL (PDF-001)."""
    pdf_file = tmp_path / "broken.pdf"
    img_file = tmp_path / "img.png"
    create_broken_digital_pdf(pdf_file, img_file)

    pdf = pdfium.PdfDocument(pdf_file)
    meta = classify_pdf_page(pdf[0], 1)
    assert meta.classification == PageClassification.BROKEN_DIGITAL
    assert meta.details["is_broken"] is True


def test_broken_digital_falls_back_to_ocr(tmp_path: Path):
    """Verify that a broken-digital page falls back to OCR and recovers legible text (PDF-005)."""
    pdf_file = tmp_path / "broken_fallback.pdf"
    img_file = tmp_path / "img_fallback.png"
    create_broken_digital_pdf(pdf_file, img_file)

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc_ir = importer.import_document(pdf_file, ws)

    assert doc_ir.metadata.page_count == 1
    # Page must have been classified as broken digital
    assert doc_ir.pages[0].classification == PageClassification.BROKEN_DIGITAL

    # Blocks should come from OCR fallback rather than garbled native text
    ocr_blocks = [b for b in doc_ir.blocks if b.extraction_method == ExtractionMethod.OCR_FAST]
    assert len(ocr_blocks) > 0

    full_text = " ".join(b.text for b in ocr_blocks if b.text)
    assert "Promissory Estoppel" in full_text or "Equity" in full_text
    assert "\ufffd\ufffd\ufffd" not in full_text
