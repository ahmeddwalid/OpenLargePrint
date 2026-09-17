"""Tests for mixed page native-text and OCR reconciliation (PDF-004)."""

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


def create_mixed_page_pdf(pdf_path: Path, img_path: Path):
    """Create a page with native digital text in column 1 and a raster scan figure in column 2."""
    # 1. Create a scanned figure with text for Column 2
    img = Image.new("RGB", (600, 500), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 50), "Figure 3.2: Flow of Appellate Jurisdictions", fill="black")
    draw.text((40, 150), "High Court -> Court of Appeal -> Supreme Court", fill="black")
    img.save(img_path)

    # 2. PDF with native text in top section and large image in bottom section (covering > 60% of page area)
    c = canvas.Canvas(str(pdf_path), pagesize=letter)

    # Native text at top of page (y=700..760)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Appellate Procedure In Criminal Matters")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Leave to appeal must be sought within twenty-eight days of conviction.")
    c.drawString(50, 710, "The appellate jurisdiction is exercised in accordance with statutory provisions.")

    # Scanned raster image covering > 60% of page area (width 500, height 600, area 300,000 / 484,704 = 0.619)
    # Image is at y=80..680, completely separate from native text at y=710..750
    c.drawImage(str(img_path), 50, 80, width=500, height=600)
    c.showPage()
    c.save()


def test_mixed_page_reconciliation(tmp_path: Path):
    """Verify that mixed pages reconcile native text and non-overlapping OCR text without duplication (PDF-004)."""
    pdf_file = tmp_path / "mixed_doc.pdf"
    img_file = tmp_path / "figure.png"
    create_mixed_page_pdf(pdf_file, img_file)

    pdf = pdfium.PdfDocument(pdf_file)
    meta = classify_pdf_page(pdf[0], 1)
    assert meta.classification == PageClassification.MIXED

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc_ir = importer.import_document(pdf_file, ws)

    assert doc_ir.metadata.page_count == 1
    assert doc_ir.pages[0].classification == PageClassification.MIXED

    # Verify both native text and OCR text are present
    native_blocks = [b for b in doc_ir.blocks if b.extraction_method == ExtractionMethod.NATIVE and b.text]
    ocr_blocks = [b for b in doc_ir.blocks if b.extraction_method == ExtractionMethod.OCR_FAST and b.text]

    assert len(native_blocks) > 0, "Native text must be preserved"
    assert len(ocr_blocks) > 0, "OCR text from figure should be extracted"

    # Verify native text content
    native_full = " ".join(b.text for b in native_blocks)
    assert "Appellate Procedure" in native_full
    assert "twenty-eight days" in native_full

    # Verify OCR text from figure
    ocr_full = " ".join(b.text for b in ocr_blocks)
    assert "Appellate Jurisdictions" in ocr_full or "Court of Appeal" in ocr_full or "Supreme Court" in ocr_full

    # Verify no native text duplicated in OCR blocks (Principle 1)
    assert "twenty-eight days" not in ocr_full
