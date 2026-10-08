"""PDF engine building blocks: words, hidden layers, blanks, glyphs, tables, order (PDF-001..006, TBL-001, OCR-004).

Layout-model-independent: every importer here gets the geometric detector, so
the results do not depend on whether the model weights are installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import pytest
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from openlargeprint.exporters.fonts import bundled_font_dir
from openlargeprint.importers.pdf.assemble import (
    BLANK_TEXT,
    PageAssembler,
    _label_captions,
    insert_blanks,
    xy_cut_order,
)
from openlargeprint.importers.pdf.glyphs import clean_recognized_text, map_symbol_char
from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.importers.pdf.rules import Rule
from openlargeprint.importers.pdf.tables import build_table, ruled_table_regions
from openlargeprint.importers.pdf.textlayer import Word
from openlargeprint.ir.models import (
    SCHEMA_VERSION,
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    InlineStyle,
    PageClassification,
    PageMetadata,
)
from openlargeprint.layout.detector import HeuristicLayoutDetector
from openlargeprint.layout.regions import LayoutRegion, RegionKind
from openlargeprint.ocr.base import EngineCapabilities, EnginePageResult, OcrDetectedLine
from openlargeprint.security.isolation import JobWorkspace


class RecordingOcr:
    """Stands in for the recogniser: records calls and returns fixed lines."""

    def __init__(self, lines: Optional[List[Tuple[str, Tuple[float, float, float, float], float]]] = None):
        self.calls = 0
        self._lines = lines or []

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities("test", False, True, ["en"])

    def analyze_page(self, image, *, page_num, language_hints=("en",), cancellation=None) -> EnginePageResult:
        self.calls += 1
        return EnginePageResult(lines=[
            OcrDetectedLine(text=text, polygon=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)], confidence=conf)
            for text, (x0, y0, x1, y1), conf in self._lines])


def _import(pdf: Path, ocr=None) -> DocumentIR:
    importer = NativePdfImporter(ocr_engine=ocr, layout_detector=HeuristicLayoutDetector())
    with JobWorkspace() as workspace:
        return importer.import_document(pdf, workspace)


def _texts(doc: DocumentIR) -> List[str]:
    return [b.text for b in doc.blocks if b.text]


def _word(text: str, x0: float, y0: float, size: float = 10.0, bold: bool = False, conf: float = 1.0) -> Word:
    return Word(text, x0, y0, x0 + 0.5 * size * len(text), y0 + size, size=size, bold=bold, confidence=conf)


# -- native words ---------------------------------------------------------------

def test_letter_spaced_heading_stays_one_word_and_spaces_are_kept(tmp_path: Path):
    pdf = tmp_path / "spacing.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    text = c.beginText(72, 760)
    text.setFont("Helvetica-Bold", 18)
    text.setCharSpace(4)
    text.textLine("CHAPTER ONE")
    c.drawText(text)
    c.setFont("Helvetica", 11)
    c.drawString(72, 720, "The tenant shall pay the rent monthly.")
    c.save()

    texts = _texts(_import(pdf))
    assert "CHAPTER ONE" in texts
    assert "The tenant shall pay the rent monthly." in texts


def test_ligature_glyphs_are_read_as_their_letters(tmp_path: Path):
    font_path = bundled_font_dir() / "DejaVuSans.ttf"
    pdfmetrics.registerFont(TTFont("DejaVuTest", str(font_path)))
    pdf = tmp_path / "ligature.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFont("DejaVuTest", 12)
    c.drawString(72, 760, "The ﬁnal oﬃce ﬂoor.")
    c.save()

    assert "The final office floor." in _texts(_import(pdf))


def test_invisible_text_layer_sends_the_page_to_recognition(tmp_path: Path):
    """An OCR layer from another tool (render mode 3) is not trusted as the page's text (PDF-003)."""
    pdf = tmp_path / "hidden.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    text = c.beginText(72, 760)
    text.setTextRenderMode(3)
    text.setFont("Helvetica", 12)
    text.textLine("Old recognition output with mistakes")
    c.drawText(text)
    c.save()

    ocr = RecordingOcr([("Recognised again", (300, 300, 1200, 360), 0.97)])
    doc = _import(pdf, ocr)
    assert ocr.calls >= 1
    assert doc.pages[0].classification == PageClassification.SCANNED
    assert doc.pages[0].details.get("hidden_text_layer") is True
    texts = _texts(doc)
    assert "Recognised again" in texts
    assert not any("Old recognition" in t for t in texts)


def test_text_under_a_full_page_picture_is_treated_as_hidden(tmp_path: Path):
    page_image = tmp_path / "scan.png"
    Image.new("RGB", (600, 840), "white").save(page_image)
    pdf = tmp_path / "under.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "Text painted before the scan covers it")
    c.drawImage(str(page_image), 0, 0, *A4)
    c.save()

    ocr = RecordingOcr()
    doc = _import(pdf, ocr)
    assert ocr.calls >= 1
    assert doc.pages[0].details.get("hidden_text_layer") is True
    assert not any("Text painted" in t for t in _texts(doc))


def test_visible_native_text_is_never_recognised(tmp_path: Path):
    """PDF-002: a page with real text never reaches the recogniser."""
    pdf = tmp_path / "native.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "Article 1. Every person is equal before the law.")
    c.save()

    ocr = RecordingOcr([("WRONG", (0, 0, 10, 10), 0.99)])
    doc = _import(pdf, ocr)
    assert ocr.calls == 0
    assert doc.pages[0].classification == PageClassification.NATIVE
    assert all(b.extraction_method == ExtractionMethod.NATIVE for b in doc.blocks if b.text)


def test_picture_only_scan_is_kept_as_a_picture_without_alarm(tmp_path: Path):
    page_image = tmp_path / "photo.png"
    Image.new("RGB", (600, 840), (120, 160, 200)).save(page_image)
    pdf = tmp_path / "photo.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.drawImage(str(page_image), 0, 0, *A4)
    c.save()

    doc = _import(pdf, RecordingOcr())
    pictures = [b for b in doc.blocks if b.type == BlockType.IMAGE]
    assert len(pictures) == 1
    assert pictures[0].warnings == []
    assert pictures[0].source_bounding_box is not None


def test_bold_words_inside_a_sentence_become_emphasis(tmp_path: Path):
    pdf = tmp_path / "emphasis.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "A")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72 + c.stringWidth("A ", "Helvetica", 12), 760, "contract")
    c.setFont("Helvetica", 12)
    x = 72 + c.stringWidth("A ", "Helvetica", 12) + c.stringWidth("contract ", "Helvetica-Bold", 12)
    c.drawString(x, 760, "binds the parties who sign it.")
    c.save()

    block = next(b for b in _import(pdf).blocks if b.text and "binds" in b.text)
    assert block.text == "A contract binds the parties who sign it."
    bold = [s for s in block.styles if s.bold]
    assert [block.text[s.start:s.end] for s in bold] == ["contract"]


def test_dialogue_lines_become_items_with_speakers(tmp_path: Path):
    pdf = tmp_path / "dialogue.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "A: Have you read the lease?")
    c.drawString(72, 742, "B: Yes, and I have a question about clause four.")
    c.save()

    items = [b for b in _import(pdf).blocks if b.type == BlockType.LIST]
    assert [b.list_marker for b in items] == ["A:", "B:"]
    assert all(b.role == "dialogue" for b in items)


# -- glyphs ------------------------------------------------------------------------

def test_symbol_fonts_map_to_standard_characters():
    assert map_symbol_char("", "Wingdings-Regular") == "✓"
    assert map_symbol_char("", "ABCDEF+Wingdings") == "□"
    assert map_symbol_char("", "Symbol") == "•"
    assert map_symbol_char("", "SomeTextbookFont") == "•"  # unknown private-use marker stays visible
    assert map_symbol_char("a", "Wingdings") is None
    assert map_symbol_char("é", "Times") is None
    assert clean_recognized_text(" Tick the box") == "• Tick the box"
    assert clean_recognized_text("plain text") == "plain text"


# -- blanks and underlines -----------------------------------------------------------

def test_answer_line_between_words_becomes_a_blank():
    words = [_word("She", 72, 100), _word("to", 200, 100), _word("school.", 214, 100)]
    rule = Rule(95, 109.5, 195, 110.5)
    result = insert_blanks(words, [rule], [], 595)
    blanks = [w for w in result if w.blank]
    assert len(blanks) == 1 and blanks[0].text == BLANK_TEXT
    assert not any(w.underline for w in words)


def test_line_under_words_is_an_underline_not_a_blank():
    words = [_word("Read", 72, 100), _word("carefully", 98, 100)]
    rule = Rule(72, 109, 98 + 0.5 * 10 * len("carefully"), 110.5)
    result = insert_blanks(words, [rule], [], 595)
    assert not any(w.blank for w in result)
    assert all(w.underline for w in words)


def test_contents_dot_leader_is_not_a_blank():
    words = [_word("Introduction", 72, 100), _word("7", 400, 100)]
    region = LayoutRegion(RegionKind.CONTENTS, 60, 90, 420, 120)
    rule = Rule(140, 109.5, 395, 110.5)
    result = insert_blanks(words, [rule], [region], 595)
    assert not any(w.blank for w in result)


# -- tables ------------------------------------------------------------------------

def _grid_words(rows: List[List[str]], xs: List[float], top: float = 100, step: float = 20,
                bold_header: bool = True) -> List[Word]:
    words = []
    for r, row in enumerate(rows):
        for text, x in zip(row, xs):
            words.append(_word(text, x, top + r * step, bold=bold_header and r == 0))
    return words


def test_ruled_table_uses_its_lines():
    rows = [["Case", "Year", "Court"], ["Hyde", "1840", "High"], ["Carlill", "1893", "Appeal"]]
    words = _grid_words(rows, [80, 220, 360])
    rules = [Rule(70, 95, 71, 160, vertical=True), Rule(210, 95, 211, 160, vertical=True),
             Rule(350, 95, 351, 160, vertical=True), Rule(470, 95, 471, 160, vertical=True)]
    rules += [Rule(70, y, 471, y + 1) for y in (95, 117, 137, 159)]
    region = LayoutRegion(RegionKind.TABLE, 70, 95, 471, 160)
    structure, confidence = build_table(region, words, rules)
    assert [[c.text for c in row] for row in structure.rows] == rows
    assert structure.has_header
    assert confidence >= 0.9


def test_unruled_table_columns_come_from_white_space():
    rows = [["Term", "Meaning"], ["Offer", "A promise"], ["Accept", "Agreement"]]
    words = _grid_words(rows, [80, 260])
    region = LayoutRegion(RegionKind.TABLE, 75, 95, 400, 160)
    structure, _ = build_table(region, words, [])
    assert [[c.text for c in row] for row in structure.rows] == rows


def test_ruled_grid_found_without_layout_model_and_prose_is_left_alone():
    words = _grid_words([["Milestone", "Due", "Status"], ["Draft", "30", "Done"]], [90, 320, 580],
                        top=140, step=60)
    verticals = [Rule(x, 120, x + 1, 270, vertical=True) for x in (80, 300, 560, 820)]
    horizontals = [Rule(80, y, 821, y + 1) for y in (120, 180, 270)]
    found = ruled_table_regions(verticals + horizontals, words)
    assert len(found) == 1 and found[0].kind == RegionKind.TABLE

    # A single box drawn around a paragraph is not a table.
    box = [Rule(80, 120, 81, 270, vertical=True), Rule(820, 120, 821, 270, vertical=True)] + horizontals[::2]
    assert ruled_table_regions(box, words) == []


# -- reading order and furniture -----------------------------------------------------

def test_xy_cut_reads_uneven_columns_column_by_column():
    boxes = [
        (50, 40, 550, 60),     # 0 full-width title
        (50, 80, 280, 140),    # 1 left column, top
        (320, 80, 550, 140),   # 2 right column, top
        (50, 160, 280, 260),   # 3 left column continues below the right column's end
        (50, 700, 550, 720),   # 4 full-width footnote
    ]
    assert xy_cut_order(boxes) == [0, 1, 3, 2, 4]
    assert xy_cut_order(boxes, rtl=True) == [0, 2, 1, 3, 4]


def test_running_heads_and_page_numbers_move_to_page_details():
    pages = [PageMetadata(page_number=n, width=595, height=842, classification=PageClassification.NATIVE)
             for n in (1, 2, 3)]
    blocks = []
    for n in (1, 2, 3):
        blocks.append(Block(id=f"h{n}", type=BlockType.ASIDE, text="Law of Contract", role="running_text", source_page=n))
        blocks.append(Block(id=f"n{n}", type=BlockType.ASIDE, text=str(40 + n), role="page_number", source_page=n))
        blocks.append(Block(id=f"p{n}", type=BlockType.PARAGRAPH, text=f"Body of page {n}.", source_page=n))
    blocks.append(Block(id="once", type=BlockType.ASIDE, text="See also chapter 9", role="running_text", source_page=2))

    kept = NativePdfImporter._settle_page_furniture(blocks, pages)
    assert [b.id for b in kept] == ["p1", "p2", "p3", "once"]
    assert next(b for b in kept if b.id == "once").role == "page_note"
    assert pages[0].details["printed_page"] == "41"
    assert pages[2].details["running_text"] == ["Law of Contract"]


def test_figure_line_next_to_a_picture_becomes_its_caption():
    blocks = [
        Block(id="i", type=BlockType.IMAGE, source_page=1),
        Block(id="c", type=BlockType.PARAGRAPH, text="Figure 4.1: Hierarchy of review.", source_page=1),
        Block(id="p", type=BlockType.PARAGRAPH, text="Figure 2 shows the court system.", source_page=1),
    ]
    _label_captions(blocks)
    assert [b.type for b in blocks] == [BlockType.IMAGE, BlockType.CAPTION, BlockType.PARAGRAPH]


def test_picture_text_is_kept_as_figure_text():
    assembler = PageAssembler(1, 595, 842, ExtractionMethod.NATIVE)
    region = LayoutRegion(RegionKind.FIGURE, 100, 100, 400, 300, order=0)
    words = [_word("EXIT", 200, 150, conf=0.95), _word("ONLY", 240, 150, conf=0.95)]
    page = assembler.assemble([region], words, lambda r: None, lambda r, w: None)
    caption = next(b for b in page.blocks if b.type == BlockType.CAPTION)
    assert caption.text == "EXIT ONLY"
    assert caption.role == "figure_text"
    assert caption.source_bounding_box is not None


# -- schema -------------------------------------------------------------------------

def test_ir_1_1_fields_round_trip():
    block = Block(id="b", type=BlockType.LIST, text="1 Fill in ______ here.\nSecond line", source_page=3,
                  list_marker="1", indent_level=2, role="dialogue",
                  styles=[InlineStyle(start=2, end=6, bold=True, underline=True)])
    doc = DocumentIR(metadata=DocumentMetadata(title="t", page_count=3), blocks=[block])
    again = DocumentIR.model_validate_json(doc.model_dump_json())
    assert again.schema_version == SCHEMA_VERSION == "1.1.0"
    assert again.blocks[0] == block
    with pytest.raises(ValueError):
        Block(id="x", type=BlockType.PARAGRAPH, source_page=1, indent_level=9)


# -- rotated pages (PDF-007) ----------------------------------------------------------

def _rotated_copy(source: Path, target: Path, degrees: int) -> Path:
    import pikepdf

    with pikepdf.open(source) as pdf:
        pdf.pages[0].Rotate = degrees
        pdf.save(target)
    return target


@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_text_shown_sideways_is_read_in_its_own_direction(tmp_path: Path, degrees: int):
    """A page whose text runs down or up the screen must not become letter salad."""
    source = tmp_path / "upright.pdf"
    c = canvas.Canvas(str(source), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "First line of the turned page.")
    c.drawString(72, 740, "Second line follows it.")
    c.save()
    doc = _import(_rotated_copy(source, tmp_path / f"r{degrees}.pdf", degrees))
    assert "First line of the turned page. Second line follows it." in _texts(doc)
    assert doc.pages[0].details.get("reading_rotation") in (90, 180, 270)


def test_landscape_page_made_upright_by_rotate_reads_normally(tmp_path: Path):
    """The usual landscape page: content drawn turned, /Rotate shows it upright."""
    source = tmp_path / "landscape.pdf"
    c = canvas.Canvas(str(source), pagesize=A4)
    c.translate(A4[0], 0)
    c.rotate(90)  # text runs up the unrotated page
    c.setFont("Helvetica", 12)
    c.drawString(72, 500, "Landscape page text reads across.")
    c.save()
    doc = _import(_rotated_copy(source, tmp_path / "landscape_rotated.pdf", 90))
    assert "Landscape page text reads across." in _texts(doc)
    assert "reading_rotation" not in doc.pages[0].details
    assert doc.pages[0].width > doc.pages[0].height


def test_picture_on_rotated_page_keeps_its_place(tmp_path: Path):
    picture = tmp_path / "pic.png"
    Image.new("RGB", (120, 80), (200, 30, 30)).save(picture)
    source = tmp_path / "pic.pdf"
    c = canvas.Canvas(str(source), pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(6):
        c.drawString(72, 780 - 16 * i, f"Line {i} of text above the picture on this page.")
    c.drawImage(str(picture), 72, 500, 120, 80)
    c.drawString(72, 470, "Text below the picture.")
    c.save()
    importer = NativePdfImporter(layout_detector=HeuristicLayoutDetector())
    with JobWorkspace() as workspace:
        doc = importer.import_document(_rotated_copy(source, tmp_path / "pic90.pdf", 90), workspace)
        blocks = [b for b in doc.blocks if b.type != BlockType.PAGE_MARKER]
        kinds = [b.type for b in blocks]
        assert BlockType.IMAGE in kinds
        image_at = kinds.index(BlockType.IMAGE)
        after = [b.text for b in blocks[image_at + 1:] if b.text]
        assert any("Text below the picture." in t for t in after)
        with Image.open(blocks[image_at].image_asset.file_path) as img:
            assert img.size == (120, 80)  # original pixels, not a sideways render


# -- recognition routing (OCR-001, LANG-002) --------------------------------------------

def _scan_pdf(path: Path) -> Path:
    page_image = path.with_suffix(".png")
    Image.new("RGB", (600, 840), "white").save(page_image)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(str(page_image), 0, 0, *A4)
    c.save()
    return path


def _route(monkeypatch, engines):
    from openlargeprint.ocr.router import OcrRouter

    monkeypatch.setattr(OcrRouter, "get_engine", lambda self, mode=None, language="en": engines[language])


class FailingOcr(RecordingOcr):
    def analyze_page(self, image, **kwargs):
        self.calls += 1
        raise FileNotFoundError("model not installed")


def test_arabic_file_name_with_latin_scan_keeps_the_better_reading(tmp_path: Path, monkeypatch):
    """A file name is only a guess: a weak Arabic reading is compared with the Latin one."""
    arabic = RecordingOcr([("ـــ", (300, 300, 1200, 360), 0.31)])
    latin = RecordingOcr([("Judicial review", (300, 300, 1200, 360), 0.96)])
    _route(monkeypatch, {"ar": arabic, "en": latin})
    importer = NativePdfImporter(layout_detector=HeuristicLayoutDetector())
    with JobWorkspace() as workspace:
        doc = importer.import_document(_scan_pdf(tmp_path / "قراءة كتاب.pdf"), workspace)
    assert arabic.calls == 1 and latin.calls == 1
    assert "Judicial review" in _texts(doc)


def test_missing_arabic_recogniser_falls_back_instead_of_losing_the_page(tmp_path: Path, monkeypatch):
    arabic = FailingOcr()
    latin = RecordingOcr([("Judicial review", (300, 300, 1200, 360), 0.96)])
    _route(monkeypatch, {"ar": arabic, "en": latin})
    importer = NativePdfImporter(layout_detector=HeuristicLayoutDetector())
    with JobWorkspace() as workspace:
        doc = importer.import_document(_scan_pdf(tmp_path / "قراءة كتاب.pdf"), workspace)
    assert "Judicial review" in _texts(doc)
    assert not any(b.id.endswith("_retained") for b in doc.blocks)


def test_table_region_without_words_is_kept_as_a_picture():
    """A table pasted into the page as an image must not vanish (never drop content)."""
    assembler = PageAssembler(1, 595, 842, ExtractionMethod.NATIVE)
    table = LayoutRegion(RegionKind.TABLE, 72, 100, 500, 300, order=0, label="table")
    made = []

    def make_figure(region):
        made.append(region)
        from openlargeprint.ir.models import ImageAsset
        return ImageAsset(asset_id="t", file_path="t.png", width=10, height=10)

    page = assembler.assemble([table], [], make_figure, lambda r, w: None)
    assert made == [table]
    assert [b.type for b in page.blocks] == [BlockType.IMAGE]


class OneRegionLayout:
    """Stands in for the layout model: the given regions, in the given order."""

    name = "test"

    def __init__(self, regions):
        self._regions = regions

    def detect(self, image, page_width, page_height):
        from openlargeprint.layout.regions import PageLayout

        return PageLayout(width=page_width, height=page_height, regions=list(self._regions), source="model")


def test_heading_drawn_as_outlines_is_recognised_on_a_text_page(tmp_path: Path):
    """Text set as vector curves has no characters; its layout region is recognised instead."""
    pdf = tmp_path / "outlined.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.rect(72, 760, 300, 30, fill=1)  # stands in for a heading drawn as curves
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "Body text that the page does contain as characters.")
    c.save()
    regions = [LayoutRegion(RegionKind.HEADING, 70, 50, 380, 84, order=0, label="paragraph_title"),
               LayoutRegion(RegionKind.TEXT, 70, 128, 520, 146, order=1, label="text")]
    ocr = RecordingOcr([("Chapter One", (10, 10, 400, 60), 0.97)])
    importer = NativePdfImporter(ocr_engine=ocr, layout_detector=OneRegionLayout(regions))
    with JobWorkspace() as workspace:
        doc = importer.import_document(pdf, workspace)
    texts = _texts(doc)
    assert ocr.calls == 1  # only the empty heading region, never the native text
    assert texts.index("Chapter One") < texts.index("Body text that the page does contain as characters.")
