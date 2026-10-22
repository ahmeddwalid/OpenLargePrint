"""Tests for native PDF text extraction, column ordering, and provenance (PDF-002, PDF-006, OUT-005)."""

import shutil

import pytest
from pathlib import Path
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


def test_line_aggregation_and_bullet_normalization(tmp_path: Path):
    """Verify that fragmented words on the same line are unified and lone bullets normalize (PDF-002)."""
    pdf_path = tmp_path / "fragments_and_bullets.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    
    # Draw disjoint words across a single horizontal baseline (y=700)
    c.setFont("Helvetica", 12)
    c.drawString(50, 700, "The")
    c.drawString(75, 700, "quick")
    c.drawString(108, 700, "brown")
    c.drawString(145, 700, "fox")
    c.drawString(170, 700, "jumps.")

    # Draw a lone bullet on line y=660 followed by text
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 660, "•")
    c.setFont("Helvetica", 12)
    c.drawString(65, 660, "Itemized point about document structure.")

    c.showPage()
    c.save()

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc = importer.import_document(pdf_path, ws)

    content_blocks = [b for b in doc.blocks if b.type != BlockType.PAGE_MARKER]
    
    # The words on y=700 should be aggregated into one cohesive line/paragraph
    fox_blocks = [b for b in content_blocks if "quick brown fox jumps" in (b.text or "")]
    assert len(fox_blocks) == 1, "Disjoint horizontal words should be aggregated into a single block"

    # The bullet character should normalize into a LIST item, not a standalone HEADING
    bullet_blocks = [b for b in content_blocks if "Itemized point" in (b.text or "")]
    assert len(bullet_blocks) == 1
    assert bullet_blocks[0].type == BlockType.LIST



# --- multi-letter Arabic glyphs ----------------------------------------------

def _cluster_chars(spec):
    from openlargeprint.importers.pdf.textlayer import _Char
    return [_Char(ch, x0, 0.0, x1, 12.0, 10.0, 10.0, False, False, space, "Noto")
            for ch, x0, x1, space in spec]


def test_lam_alef_ligature_keeps_its_reading_order():
    # PDFium's report for "لا يجوز ... إلا" set by LibreOffice: each ligature's two
    # letters share one box and arrive reversed.
    from openlargeprint.importers.pdf.textlayer import _chars_to_words, _restore_clusters
    chars = _cluster_chars([
        ("ي", 209.7, 212.9, False), ("ج", 202.9, 210.1, False), ("و", 198.5, 203.3, False),
        ("ز", 194.0, 198.5, False),
        ("إ", 165.9, 168.7, True), ("ا", 160.5, 165.8, False), ("ل", 160.5, 165.8, False),
        ("ف", 108.1, 112.2, True), ("ن", 97.1, 108.4, False), ("ي", 97.1, 108.4, False),
    ])
    words = [w.text for w in _chars_to_words(_restore_clusters(chars))]
    assert words == ["يجوز", "إلا", "فين"]


def test_word_start_ligature_keeps_the_space_before_it():
    from openlargeprint.importers.pdf.textlayer import _chars_to_words, _restore_clusters
    chars = _cluster_chars([
        ("ق", 74.7, 78.7, False), ("ا", 71.8, 75.0, False), ("ل", 65.1, 71.8, False),
        ("ا", 56.7, 62.1, True), ("ل", 56.7, 62.1, False),
    ])
    assert [w.text for w in _chars_to_words(_restore_clusters(chars))] == ["قال", "لا"]


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_libreoffice_arabic_ligatures_round_trip(tmp_path):
    import subprocess
    import pypdfium2 as pdfium
    from openlargeprint.importers.pdf.textlayer import PageFrame, extract_native_text
    sentence = "لا يجوز نقضه إلا باتفاق الطرفين فلا تعديل"
    html = tmp_path / "ar.html"
    html.write_text(f'<html><body dir="rtl"><p>{sentence}</p></body></html>', encoding="utf-8")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(html)],
                   check=True, capture_output=True, timeout=180)
    page = pdfium.PdfDocument(str(tmp_path / "ar.pdf"))[0]
    words = extract_native_text(page, page.get_textpage(), PageFrame(page)).words
    assert set(sentence.split()) == {w.text for w in words}


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_libreoffice_arabic_page_reads_exactly(tmp_path):
    """Vowel marks, punctuation, numbers, brackets and a list, as LibreOffice writes them."""
    import subprocess
    from openlargeprint.security.isolation import JobWorkspace as Workspace
    paragraphs = [
        "المادة ١٤٧: العقد شريعة المتعاقدين، فلا يجوز نقضه ولا تعديله إلا باتفاق الطرفين، "
        "أو للأسباب التي يقررها القانون (انظر المادة 148).",
        "لا يقتصر العقد على إلزام المتعاقد بما ورد فيه، ولكن يتناول أيضًا ما هو من مستلزماته "
        "وفقًا للقانون والعرف والعدالة.",
    ]
    html = tmp_path / "ar.html"
    html.write_text('<html><body dir="rtl"><h1>الباب الأول: أحكام عامة</h1>'
                    + "".join(f"<p>{p}</p>" for p in paragraphs)
                    + "<ul><li>البند الأول: الالتزام بالتسليم</li><li>البند الثاني: الالتزام بالضمان</li></ul>"
                    "</body></html>", encoding="utf-8")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(html)],
                   check=True, capture_output=True, timeout=180)
    with Workspace() as workspace:
        doc = NativePdfImporter().import_document(tmp_path / "ar.pdf", workspace)
    import unicodedata
    # A vowel mark may be stored after the alef rather than before it; both read the same.
    canon = lambda t: unicodedata.normalize("NFC", t).replace("ًا", "اً")
    texts = [canon(b.text) for b in doc.blocks if b.text]
    for expected in ["الباب الأول: أحكام عامة", *paragraphs]:
        assert canon(expected) in texts, texts
    assert not any(b.type == BlockType.IMAGE for b in doc.blocks)
