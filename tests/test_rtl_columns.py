"""Tests for RTL multi-column reading order reconstruction (PDF-003, LANG-002)."""

from pathlib import Path
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

    # Glyphs are drawn right to left, so whole words come back in reading order
    # (the source characters themselves are never altered).
    for phrase in ("لا مساغ للاجتهاد في مورد النص", "القديم يترك على قدمه", "الضرر لا يزال بمثله"):
        assert phrase in full_text

    # The right-hand column is read completely before the left-hand one.
    article = [full_text.find(p) for p in ("مساغ للاجتهاد", "باليقين", "الأصل بقاء", "القديم يترك", "الضرر لا", "درء المفاسد")]
    assert all(pos != -1 for pos in article)
    assert article == sorted(article), "Right column (articles 1-3) must precede the left column (articles 4-6)"
    assert full_text.find("مجلة الأحكام") < article[0], "The title comes first"
