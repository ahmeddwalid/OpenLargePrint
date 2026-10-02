"""Tests for RTL multi-column reading order reconstruction (PDF-003, LANG-002)."""

from pathlib import Path
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import BlockType, TextDirection
from openlargeprint.security.isolation import JobWorkspace
from openlargeprint.text.bidi import reorder_bidi_for_display


def create_two_column_arabic_pdf(pdf_path: Path):
    """Create a two-column Arabic legal document.
    
    In Arabic typography:
    - Column 1 is on the RIGHT (higher X coordinates, e.g. x=330..550)
    - Column 2 is on the LEFT (lower X coordinates, e.g. x=50..270)
    Reading order MUST read Right Column before Left Column (LANG-002).
    """
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

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    
    # Header across full width
    c.setFont(font_name, 16)
    title = "مجلة الأحكام العدلية: الباب التمهيدي"
    c.drawString(100, 720, reorder_bidi_for_display(title, TextDirection.RTL))

    c.setFont(font_name, 10)
    # Column 1 (RIGHT COLUMN: x=330..550, y=650..400)
    c.drawString(330, 650, reorder_bidi_for_display("المادة ١: لا مساغ للاجتهاد في مورد النص.", TextDirection.RTL))
    c.drawString(330, 620, reorder_bidi_for_display("المادة ٢: ما ثبت باليقين لا يزول بالشك.", TextDirection.RTL))
    c.drawString(330, 590, reorder_bidi_for_display("المادة ٣: الأصل بقاء ما كان على ما كان.", TextDirection.RTL))

    # Column 2 (LEFT COLUMN: x=50..270, y=650..400)
    c.drawString(50, 650, reorder_bidi_for_display("المادة ٤: القديم يترك على قدمه.", TextDirection.RTL))
    c.drawString(50, 620, reorder_bidi_for_display("المادة ٥: الضرر لا يزال بمثله.", TextDirection.RTL))
    c.drawString(50, 590, reorder_bidi_for_display("المادة ٦: درء المفاسد أولى من جلب المنافع.", TextDirection.RTL))

    # Footer across full width
    c.drawString(150, 100, reorder_bidi_for_display("انتهى الباب التمهيدي ويليه كتاب البيوع.", TextDirection.RTL))

    c.showPage()
    c.save()


def test_rtl_multi_column_reading_order(tmp_path: Path):
    """Verify that multi-column Arabic pages read Column 1 (Right) before Column 2 (Left) (LANG-002)."""
    pdf_path = tmp_path / "arabic_two_column.pdf"
    create_two_column_arabic_pdf(pdf_path)

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc_ir = importer.import_document(pdf_path, ws)

    # Filter text-bearing blocks
    text_blocks = [b for b in doc_ir.blocks if b.type != BlockType.PAGE_MARKER and b.text]
    assert len(text_blocks) >= 3

    # All Arabic blocks must have RTL direction and 'ar' language (LANG-001)
    for b in text_blocks:
        assert b.text_direction == TextDirection.RTL
        assert b.language == "ar"

    full_text = " ".join(b.text for b in text_blocks)

    # This fixture deliberately embeds display-order presentation forms, not
    # logical Unicode. Native import must preserve those source characters;
    # guessing words to reverse also corrupts valid logical Arabic (PDF-002).
    # PDFium can normalize presentation glyph mappings itself. Its extracted
    # source stream is the native-character oracle, independent of our grouping.
    with pdfium.PdfDocument(pdf_path) as source:
        page = source[0]
        text_page = page.get_textpage()
        try:
            source_lines = text_page.get_text_range().splitlines()
            right_source = next(line for line in source_lines if "للاجتهاد" in line)
            left_source = next(line for line in source_lines if "القديم" in line)
        finally:
            text_page.close()
            page.close()
    pos_right_col = full_text.find(right_source)
    pos_left_col = full_text.find(left_source)

    assert pos_right_col != -1, "Right column content must be present"
    assert pos_left_col != -1, "Left column content must be present"
    assert pos_right_col < pos_left_col, (
        f"Right column (Column 1) must be read BEFORE Left column (Column 2) in Arabic RTL documents! "
        f"pos_right={pos_right_col}, pos_left={pos_left_col}"
    )
    assert any("reading order" in warning for block in text_blocks for warning in block.warnings)
    assert any(block.image_asset for block in doc_ir.blocks), "Ambiguous native encoding retains the original page"
