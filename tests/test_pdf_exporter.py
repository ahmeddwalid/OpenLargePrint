"""Tests for reflowed large-print PDF exporter (OUT-003, OUT-007..009)."""

from pathlib import Path
import pytest
import pypdfium2 as pdfium

from openlargeprint.exporters import ExportOptions, PaperSize, PdfExporter, PresetName
from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    PageClassification,
    PageMetadata,
)


def create_sample_ir() -> DocumentIR:
    metadata = DocumentMetadata(title="Jurisprudence and the Rule of Law", page_count=1)
    pages = [
        PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)
    ]
    blocks = [
        Block(id="p1_m", type=BlockType.PAGE_MARKER, source_page=1, page_marker=1),
        Block(
            id="p1_h1",
            type=BlockType.HEADING,
            text="Section A: The Inner Morality of Law",
            level=1,
            source_page=1,
        ),
        Block(
            id="p1_b1",
            type=BlockType.PARAGRAPH,
            text="Lon Fuller posited eight essential desiderata for a legal system to function justly.",
            source_page=1,
        ),
        Block(
            id="p1_fn",
            type=BlockType.FOOTNOTE,
            text="1. See Fuller, The Morality of Law (Yale University Press, 1964).",
            source_page=1,
        ),
    ]
    return DocumentIR(metadata=metadata, pages=pages, blocks=blocks)


def test_pdf_export_a4_dimensions(tmp_path: Path):
    """Verify large-print PDF exports with true A4 physical dimensions (OUT-003, OUT-007, OUT-009)."""
    doc_ir = create_sample_ir()
    out_pdf = tmp_path / "large_print_a4.pdf"

    exporter = PdfExporter()
    options = ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4)
    exporter.export(doc_ir, out_pdf, options)

    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0

    pdf = pdfium.PdfDocument(out_pdf)
    assert len(pdf) >= 1
    page = pdf[0]
    w, h = page.get_size()

    # A4 dimensions: 595.28 x 841.89 points (210 x 297 mm)
    assert pytest.approx(w, 1.0) == 595.28
    assert pytest.approx(h, 1.0) == 841.89

    # Verify text content and print reminder footer (OUT-009)
    tp = page.get_textpage()
    text = tp.get_text_range()
    assert "Inner Morality" in text
    assert "print at 100% (actual size)" in text
    assert "Original page 1" in text


def test_pdf_export_a3_dimensions(tmp_path: Path):
    """Verify large-print PDF exports with true A3 physical dimensions (OUT-007, OUT-008)."""
    doc_ir = create_sample_ir()
    out_pdf = tmp_path / "large_print_a3.pdf"

    exporter = PdfExporter()
    options = ExportOptions(preset=PresetName.EXTRA_LARGE, paper_size=PaperSize.A3)
    exporter.export(doc_ir, out_pdf, options)

    pdf = pdfium.PdfDocument(out_pdf)
    w, h = pdf[0].get_size()

    # A3 dimensions: 841.89 x 1190.55 points (297 x 420 mm)
    assert pytest.approx(w, 1.0) == 841.89
    assert pytest.approx(h, 1.0) == 1190.55


def test_pdf_export_monochrome(tmp_path: Path):
    """Verify monochrome export produces valid high-contrast document (OUT-003)."""
    import numpy as np
    from PIL import Image

    # Create a small color test image
    img_data = np.zeros((100, 100, 3), dtype=np.uint8)
    img_data[:, :] = [255, 0, 0]  # pure red
    img_path = tmp_path / "test_color.png"
    Image.fromarray(img_data).save(img_path)

    from openlargeprint.ir.models import ImageAsset
    doc_ir = create_sample_ir()
    doc_ir.blocks.append(
        Block(
            id="p1_img",
            type=BlockType.IMAGE,
            image_asset=ImageAsset(
                asset_id="img_1",
                file_path=str(img_path),
                width=100,
                height=100,
            ),
            source_page=1,
        )
    )

    out_pdf = tmp_path / "large_print_mono.pdf"
    exporter = PdfExporter()
    options = ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4, monochrome=True)
    exporter.export(doc_ir, out_pdf, options)

    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0
    pdf = pdfium.PdfDocument(out_pdf)
    assert len(pdf) >= 1



def test_pdf_table_row_longer_than_a_page(tmp_path):
    from openlargeprint.ir.models import TableCell, TableStructure

    table = TableStructure(rows=[[TableCell(text="Clause")], [TableCell(text="Long contract provision. " * 300 + "FINAL SENTENCE")]], has_header=True)
    ir = DocumentIR(metadata=DocumentMetadata(title="Long table", page_count=1), pages=[], blocks=[Block(id="table", type=BlockType.TABLE, source_page=1, table_structure=table)])
    output = tmp_path / "long-table.pdf"
    PdfExporter().export(ir, output, ExportOptions())
    with pdfium.PdfDocument(output) as pdf:
        assert len(pdf) > 1
        text = "".join(page.get_textpage().get_text_range() for page in pdf)
        assert "FINAL SENTENCE" in " ".join(text.split())


def test_arabic_paragraph_lines_stay_in_reading_order(tmp_path):
    """Wrapped Arabic lines read top to bottom, brackets face the right way, Latin runs stay whole (LANG-001)."""
    import pypdfium2 as pdfium
    from openlargeprint.exporters import ExportOptions, PdfExporter
    from openlargeprint.ir.models import (Block, BlockType, DocumentIR, DocumentMetadata, PageClassification,
                                          PageMetadata, TextDirection)

    first = "العقد شريعة المتعاقدين"
    text = (f"{first} (المادة 147 من القانون المدني)، فلا يجوز نقضه ولا تعديله إلا باتفاق الطرفين "
            "أو للأسباب التي يقررها القانون وفقًا لـ Civil Code 2024 وما بعدها من نصوص.")
    doc = DocumentIR(
        metadata=DocumentMetadata(title="Arabic", page_count=1),
        pages=[PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)],
        blocks=[Block(id="ar", type=BlockType.PARAGRAPH, text=text, source_page=1, language="ar",
                      text_direction=TextDirection.RTL)],
    )
    out = tmp_path / "arabic.pdf"
    PdfExporter().export(doc, out, ExportOptions(include_page_markers=False))

    page = pdfium.PdfDocument(out)[0]
    textpage = page.get_textpage()
    chars = [(textpage.get_charbox(i), textpage.get_text_range(i, 1)) for i in range(textpage.count_chars())]
    lines = {}
    for (left, bottom, right, top), ch in chars:
        if ch.strip() and any("؀" <= c <= "ۿ" or c.isascii() for c in ch):
            lines.setdefault(round((top + bottom) / 2 / 8), []).append((left, ch))
    def arabic(ch):
        return "\u0600" <= ch <= "\u06ff" or "\ufb50" <= ch <= "\ufeff"

    body = [sorted(v) for k, v in sorted(lines.items(), reverse=True) if any(arabic(c) for _, c in v)]
    assert len(body) >= 2, "the paragraph should wrap onto several lines"

    painted = ["".join(ch for _, ch in line) for line in body]  # each line left to right
    assert "147" in painted[0], "the first words (with the article number) must be on the top line"
    assert all("Civil" not in line for line in painted[:1]), "later words must not jump to the top line"
    civil = next(line for line in body if any(ch == "C" for _, ch in line))
    left_to_right = "".join(ch for _, ch in civil)
    assert "CivilCode2024" in left_to_right.replace(" ", "")
