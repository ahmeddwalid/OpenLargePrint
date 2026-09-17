"""Tests for PDF page classifier (PDF-001, PDF-007)."""

import io
from pathlib import Path
from PIL import Image
import pikepdf
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.classifier import classify_pdf_page
from openlargeprint.ir.models import PageClassification


def test_classify_born_digital_page(tmp_path: Path):
    """Verify that a page with clean text and no large raster is classified as NATIVE (PDF-001)."""
    pdf_path = tmp_path / "digital.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 700, "Law School Course Syllabus")
    c.setFont("Helvetica", 11)
    for y in range(650, 200, -25):
        c.drawString(50, y, "This is standard text content discussing contractual obligations and liability.")
    c.showPage()
    c.save()

    pdf = pdfium.PdfDocument(pdf_path)
    page_meta = classify_pdf_page(pdf[0], 1)

    assert page_meta.page_number == 1
    assert page_meta.classification == PageClassification.NATIVE
    assert page_meta.details["char_count"] > 100
    assert page_meta.details["raster_coverage"] < 0.1
    assert page_meta.rotation == 0


def test_classify_scanned_page(tmp_path: Path):
    """Verify that a page with a full-page raster scan and no text is classified as SCANNED (PDF-001)."""
    # Create image
    img_path = tmp_path / "scan.png"
    img = Image.new("RGB", (600, 800), color="white")
    img.save(img_path)

    pdf_path = tmp_path / "scanned.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    # Draw image covering the entire page
    c.drawImage(str(img_path), 0, 0, width=letter[0], height=letter[1])
    c.showPage()
    c.save()

    pdf = pdfium.PdfDocument(pdf_path)
    page_meta = classify_pdf_page(pdf[0], 1)

    assert page_meta.classification == PageClassification.SCANNED
    assert page_meta.details["char_count"] == 0
    assert page_meta.details["raster_coverage"] >= 0.85


def test_classify_page_rotation(tmp_path: Path):
    """Verify that page orientation / rotation is recorded (PDF-007)."""
    pdf_path = tmp_path / "rotated.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 500, "Text on rotated page")
    c.showPage()
    c.save()

    # Rotate page using pikepdf
    pike = pikepdf.open(pdf_path)
    pike.pages[0].Rotate = 90
    rotated_path = tmp_path / "rotated_90.pdf"
    pike.save(rotated_path)
    pike.close()

    pdf = pdfium.PdfDocument(rotated_path)
    page_meta = classify_pdf_page(pdf[0], 1)

    assert page_meta.rotation == 90
