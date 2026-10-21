"""Reading font choices in every export format (OUT-001, OUT-003, LANG-001)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pikepdf
import pytest

from openlargeprint.exporters import DocxExporter, ExportOptions, PdfExporter, ReaderExporter
from openlargeprint.exporters.fonts import (
    ARABIC_FONTS,
    LATIN_FONTS,
    font_path,
    markup,
    output_fonts,
)
from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    PageClassification,
    PageMetadata,
    TextDirection,
)
from openlargeprint.text.bidi import shape_arabic

SAMPLE_ARABIC = "لا يجوز نقضه إلا باتفاق الطرفين، فلا تعديل للأستاذ ئ ة ى ؤ"


def _doc() -> DocumentIR:
    return DocumentIR(
        metadata=DocumentMetadata(title="Fonts", page_count=1),
        pages=[PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)],
        blocks=[
            Block(id="h", type=BlockType.HEADING, level=1, text="A heading", source_page=1),
            Block(id="p", type=BlockType.PARAGRAPH, text="Plain English text.", source_page=1),
            Block(id="a", type=BlockType.PARAGRAPH, text=SAMPLE_ARABIC, source_page=1,
                  text_direction=TextDirection.RTL, language="ar"),
        ],
    )


@pytest.mark.parametrize("choice", list(LATIN_FONTS.values()) + list(ARABIC_FONTS.values()),
                         ids=lambda c: c.id)
def test_every_font_choice_ships_its_files_and_license(choice):
    for style in choice.styles:
        assert font_path(choice, style).is_file(), font_path(choice, style)
    assert (font_path(choice).parent / f"{choice.file_prefix}-OFL.txt").is_file()


@pytest.mark.parametrize("font_id", list(ARABIC_FONTS))
def test_arabic_fonts_draw_every_letter_shape(font_id):
    """The PDF writer sets presentation forms, so each Arabic choice needs them all."""
    fonts = output_fonts(None, font_id)
    text = markup(shape_arabic(SAMPLE_ARABIC), fonts, fonts.arabic)
    assert "<font" not in text, f"{font_id} lacks glyphs: {text}"


def test_arabic_paragraphs_use_the_arabic_font_not_the_fallback():
    fonts = output_fonts()
    shown = markup(shape_arabic("لا يجوز abc"), fonts, fonts.arabic)
    assert fonts.fallback not in shown
    assert f'<font name="{fonts.regular}">abc' in shown  # Latin words use the Latin choice


def test_unknown_font_is_rejected():
    with pytest.raises(ValueError):
        ExportOptions(latin_font="comic-sans")
    with pytest.raises(ValueError):
        ExportOptions(arabic_font="nope")


def test_pdf_embeds_the_chosen_fonts(tmp_path: Path):
    out = PdfExporter().export(_doc(), tmp_path / "out.pdf",
                               ExportOptions(latin_font="lexend", arabic_font="amiri"))
    names = set()
    with pikepdf.open(out) as pdf:
        for page in pdf.pages:
            for font in page.Resources.Font.values():
                names.add(str(font.BaseFont))
    assert any("Lexend" in n for n in names), names
    assert any("Amiri" in n for n in names), names
    assert not any("Atkinson" in n for n in names), names


def test_word_document_names_and_embeds_the_chosen_fonts(tmp_path: Path):
    out = DocxExporter().export(_doc(), tmp_path / "out.docx",
                                ExportOptions(latin_font="noto-serif", arabic_font="noto-naskh-arabic"))
    with zipfile.ZipFile(out) as package:
        styles = package.read("word/styles.xml").decode("utf-8")
        table = package.read("word/fontTable.xml").decode("utf-8")
        parts = package.namelist()
    assert 'w:ascii="Noto Serif"' in styles and 'w:cs="Noto Naskh Arabic"' in styles
    assert "Noto Serif" in table and "Noto Naskh Arabic" in table
    assert "word/fonts/NotoSerif-Regular.odttf" in parts
    assert "word/fonts/NotoNaskhArabic-Bold.odttf" in parts


def test_reader_page_carries_the_chosen_fonts(tmp_path: Path):
    out = ReaderExporter().export(_doc(), tmp_path / "out.html",
                                  ExportOptions(latin_font="andika", arabic_font="tajawal"))
    html = out.read_text(encoding="utf-8")
    assert 'font-family: "Andika"' in html and 'font-family: "Tajawal"' in html
    assert "Atkinson" not in html


def test_interface_font_list_matches_the_engine():
    import re
    source = (Path(__file__).resolve().parent.parent / "ui" / "src" / "fonts.ts").read_text(encoding="utf-8")
    latin, arabic = source.split("export const ARABIC_FONTS")
    pairs = lambda text: re.findall(r"\{ id: '([^']+)', family: '([^']+)' \}", text)
    assert pairs(latin) == [(f.id, f.family) for f in LATIN_FONTS.values()]
    assert pairs(arabic) == [(f.id, f.family) for f in ARABIC_FONTS.values()]
