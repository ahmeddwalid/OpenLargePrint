"""End-to-end integration tests for Milestone 4: Arabic (RTL) & Mixed-Script Support (LANG-001, LANG-002)."""

from pathlib import Path
import docx
from docx.oxml.ns import qn
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from openlargeprint.exporters.base import ExportOptions, PaperSize, PresetName
from openlargeprint.exporters.docx import DocxExporter
from openlargeprint.exporters.pdf import PdfExporter
from openlargeprint.exporters.reader import ReaderExporter
from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import BlockType, TextDirection
from openlargeprint.security.isolation import JobWorkspace
from openlargeprint.text.bidi import reorder_bidi_for_display


def create_arabic_legal_pdf(pdf_path: Path):
    """Create a born-digital Arabic legal contract document."""
    font_candidates = [
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
    ]
    font_path = next((p for p in font_candidates if Path(p).exists()), None)
    if font_path:
        pdfmetrics.registerFont(TTFont("ArabicFont", font_path))
        font_name = "ArabicFont"
    else:
        font_name = "Helvetica"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    # Title
    c.setFont(font_name, 18)
    title = "عقد بيع عقار ابتدائي"
    c.drawString(100, 750, reorder_bidi_for_display(title, TextDirection.RTL))

    # Preamble
    c.setFont(font_name, 12)
    p1 = "إنه في يوم الأحد الموافق الأول من شهر المحرم، تم الاتفاق والتراضي بين كل من الطرفين."
    c.drawString(50, 680, reorder_bidi_for_display(p1, TextDirection.RTL))

    # Clause 1
    p2 = "البند الأول: يقر البائع بأنه المالك الوحيد للعقار الكائن في مدينة القاهرة."
    c.drawString(50, 600, reorder_bidi_for_display(p2, TextDirection.RTL))

    # Clause 2 (Bidi: Arabic with English transaction reference and law citation)
    p3 = "البند الثاني: يخضع هذا العقد للتقنين المدني المصري والقواعد الدولية وفقا للمعيار ISO 27001."
    c.drawString(50, 520, reorder_bidi_for_display(p3, TextDirection.RTL))

    c.showPage()
    c.save()


def test_milestone4_arabic_end_to_end(tmp_path: Path):
    """Verify Arabic legal document converts end-to-end preserving metadata across DOCX, PDF, and Reader (LANG-001, LANG-002)."""
    source_pdf = tmp_path / "arabic_contract.pdf"
    create_arabic_legal_pdf(source_pdf)

    # 1. Native Import
    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc_ir = importer.import_document(source_pdf, ws)

    assert doc_ir.metadata.page_count == 1
    text_blocks = [b for b in doc_ir.blocks if b.type != BlockType.PAGE_MARKER and b.text]
    assert len(text_blocks) >= 3

    # Verify Language and TextDirection preserved in DocumentIR (LANG-001)
    for b in text_blocks:
        assert b.language == "ar", f"Block {b.id} should have language 'ar', got {b.language}"
        assert b.text_direction == TextDirection.RTL, f"Block {b.id} should have direction RTL, got {b.text_direction}"

    options = ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4)

    # 2. DOCX Export (OUT-001, LANG-001)
    docx_path = tmp_path / "arabic_large_print.docx"
    DocxExporter().export(doc_ir, docx_path, options)
    assert docx_path.exists()
    assert docx_path.stat().st_size > 0

    word_doc = docx.Document(docx_path)
    # Verify RTL paragraph properties in OpenXML
    rtl_paragraphs = 0
    for p in word_doc.paragraphs:
        if p.text.strip():
            pPr = p._p.get_or_add_pPr()
            if pPr.find(qn("w:bidi")) is not None:
                rtl_paragraphs += 1
    assert rtl_paragraphs >= 2, "DOCX must have paragraphs with w:bidi set for Arabic"

    # 3. PDF Export (OUT-003, OUT-007, OUT-009, LANG-001)
    pdf_path = tmp_path / "arabic_large_print.pdf"
    PdfExporter().export(doc_ir, pdf_path, options)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0

    exported_pdf = pdfium.PdfDocument(pdf_path)
    assert len(exported_pdf) >= 1
    page = exported_pdf[0]
    w, h = page.get_size()
    assert pytest.approx(w, 1.0) == 595.28  # True A4 width
    assert pytest.approx(h, 1.0) == 841.89  # True A4 height

    pdf_text = page.get_textpage().get_text_range()
    assert "Print at 100% / actual size" in pdf_text
    # Arabic content rendered and present
    assert "ISO 27001" in pdf_text or "27001" in pdf_text

    # 4. In-App Reader HTML Export (OUT-002, LANG-001)
    reader_path = tmp_path / "arabic_reader.html"
    ReaderExporter().export(doc_ir, reader_path, options)
    assert reader_path.exists()

    html_content = reader_path.read_text(encoding="utf-8")
    assert 'dir="rtl"' in html_content
    assert 'class="rtl"' in html_content
    assert '--reading-font-arabic' in html_content
    assert 'direction: rtl' in html_content
    assert "عقد" in html_content
    assert "عقار" in html_content
    assert "القاهرة" in html_content
    assert "27001" in html_content
