"""Tests for large-print DOCX exporter (OUT-001, OUT-005..009, FN-002)."""

from pathlib import Path
import docx
import pytest

from conftest import effective_bold, effective_line_spacing, effective_size

from openlargeprint.exporters import (
    DocxExporter,
    ExportOptions,
    PaperSize,
    PresetName,
)
from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    PageClassification,
    PageMetadata,
)


def create_sample_ir() -> DocumentIR:
    """Create a sample DocumentIR structure for testing export."""
    metadata = DocumentMetadata(
        title="Constitutional Law Principles",
        source_file_name="conlaw.pdf",
        page_count=2,
    )
    pages = [
        PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE),
        PageMetadata(page_number=2, width=595, height=842, classification=PageClassification.NATIVE),
    ]
    blocks = [
        Block(
            id="p1_marker",
            type=BlockType.PAGE_MARKER,
            source_page=1,
            page_marker=1,
            extraction_method=ExtractionMethod.NATIVE,
        ),
        Block(
            id="p1_b1",
            type=BlockType.HEADING,
            text="Article I: The Legislative Branch",
            level=1,
            source_page=1,
            extraction_method=ExtractionMethod.NATIVE,
        ),
        Block(
            id="p1_b2",
            type=BlockType.PARAGRAPH,
            text="All legislative Powers herein granted shall be vested in a Congress.",
            source_page=1,
            extraction_method=ExtractionMethod.NATIVE,
        ),
        Block(
            id="p1_b3",
            type=BlockType.LIST,
            text="• Qualifications of Representatives",
            source_page=1,
            extraction_method=ExtractionMethod.NATIVE,
        ),
        Block(
            id="p1_b4",
            type=BlockType.FOOTNOTE,
            text="1. Compare with early parliamentary sovereignty precedents.",
            source_page=1,
            extraction_method=ExtractionMethod.NATIVE,
        ),
        Block(
            id="p2_marker",
            type=BlockType.PAGE_MARKER,
            source_page=2,
            page_marker=2,
            extraction_method=ExtractionMethod.NATIVE,
        ),
        Block(
            id="p2_b1",
            type=BlockType.PARAGRAPH,
            text="The Senate shall be composed of two Senators from each State.",
            source_page=2,
            extraction_method=ExtractionMethod.NATIVE,
        ),
    ]
    return DocumentIR(metadata=metadata, pages=pages, blocks=blocks)


def test_docx_export_large_preset_defaults(tmp_path: Path):
    """Verify that Large preset applies 20pt body font, 1.5 line spacing, and A4 page size."""
    doc_ir = create_sample_ir()
    out_file = tmp_path / "output_large.docx"
    
    exporter = DocxExporter()
    options = ExportOptions(preset=PresetName.LARGE, paper_size=PaperSize.A4)
    exporter.export(doc_ir, out_file, options)

    assert out_file.exists()
    doc = docx.Document(str(out_file))

    # 1. Section dimensions (A4: 210mm x 297mm)
    section = doc.sections[0]
    assert pytest.approx(section.page_width.mm, 1.0) == 210.0
    assert pytest.approx(section.page_height.mm, 1.0) == 297.0

    # 2. Print reminder in metadata (OUT-009)
    assert "Print at 100%" in doc.core_properties.comments

    # 3. Check paragraphs and styles
    paras = doc.paragraphs
    # Find page marker
    marker_para = next(p for p in paras if "Original page 1" in p.text)
    assert marker_para is not None

    # Find heading
    heading_para = next(p for p in paras if "Article I" in p.text)
    assert heading_para.style.name == "Heading 1"
    assert effective_bold(heading_para) is True
    # H1 is 1.55x the body size: 31pt for a 20pt body
    assert effective_size(heading_para) == pytest.approx(31.0)

    # Find body paragraph
    body_para = next(p for p in paras if "All legislative Powers" in p.text)
    assert effective_size(body_para) == pytest.approx(20.0)
    assert effective_line_spacing(body_para) == 1.5

    # Find footnote (FN-002: minimum readable size enforced)
    fn_para = next(p for p in paras if "parliamentary sovereignty" in p.text)
    assert fn_para.style.name == "Footnote Text"
    assert effective_size(fn_para) >= 14.0


def test_docx_export_a3_dimensions(tmp_path: Path):
    """Verify that A3 export applies 297mm x 420mm physical dimensions (OUT-007, OUT-008)."""
    doc_ir = create_sample_ir()
    out_file = tmp_path / "output_a3.docx"

    exporter = DocxExporter()
    options = ExportOptions(preset=PresetName.EXTRA_LARGE, paper_size=PaperSize.A3)
    exporter.export(doc_ir, out_file, options)

    doc = docx.Document(str(out_file))
    section = doc.sections[0]
    assert pytest.approx(section.page_width.mm, 1.0) == 297.0
    assert pytest.approx(section.page_height.mm, 1.0) == 420.0

    # Body font for Extra Large is 24pt
    body_para = next(p for p in doc.paragraphs if "All legislative Powers" in p.text)
    assert effective_size(body_para) == pytest.approx(24.0)


def test_docx_export_omit_page_markers(tmp_path: Path):
    """Verify that page markers can be omitted when configured (OUT-005)."""
    doc_ir = create_sample_ir()
    out_file = tmp_path / "output_no_markers.docx"

    exporter = DocxExporter()
    options = ExportOptions(include_page_markers=False)
    exporter.export(doc_ir, out_file, options)

    doc = docx.Document(str(out_file))
    marker_paras = [p for p in doc.paragraphs if "Original page" in p.text]
    assert len(marker_paras) == 0


def test_docx_export_monochrome(tmp_path: Path):
    """Verify that monochrome export processes images and text without errors (OUT-001)."""
    import numpy as np
    from PIL import Image

    img_data = np.zeros((100, 100, 3), dtype=np.uint8)
    img_data[:, :] = [0, 255, 0]  # green
    img_path = tmp_path / "test_color_docx.png"
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

    out_file = tmp_path / "output_mono.docx"
    exporter = DocxExporter()
    options = ExportOptions(monochrome=True)
    exporter.export(doc_ir, out_file, options)

    assert out_file.exists()
    assert out_file.stat().st_size > 0
    doc = docx.Document(str(out_file))
    assert len(doc.paragraphs) > 0



def test_docx_package_is_well_formed_for_word(tmp_path: Path):
    """Word rejects files whose XML children are out of schema order; LibreOffice is lenient.

    Checks element order in paragraph/table properties and settings, the embedded
    reading font (de-obfuscated it must be a TrueType file again), complex-script
    sizes for Arabic, and the quote style.
    """
    import zipfile
    from lxml import etree

    from openlargeprint.exporters.docx import _PPR_ORDER, _RPR_ORDER, _TBLPR_ORDER
    from openlargeprint.ir.models import TableCell, TableStructure, TextDirection

    doc_ir = create_sample_ir()
    doc_ir.blocks += [
        Block(id="q", type=BlockType.QUOTE, text="Quoted judgment text.", source_page=2),
        Block(id="ar", type=BlockType.PARAGRAPH, text="العقد شريعة المتعاقدين", source_page=2,
              language="ar", text_direction=TextDirection.RTL),
        Block(id="t", type=BlockType.TABLE, source_page=2, text_direction=TextDirection.RTL,
              table_structure=TableStructure(has_header=True, caption="جدول", rows=[
                  [TableCell(text="الركن", is_header=True), TableCell(text="التعريف", is_header=True)],
                  [TableCell(text="الخطأ"), TableCell(text="الإخلال")]])),
    ]
    out_file = tmp_path / "package.docx"
    DocxExporter().export(doc_ir, out_file, ExportOptions())

    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(out_file) as package:
        for part in ("word/document.xml", "word/styles.xml"):
            root = etree.fromstring(package.read(part))
            for tag, order in (("pPr", _PPR_ORDER), ("rPr", _RPR_ORDER), ("tblPr", _TBLPR_ORDER)):
                for element in root.iter(w + tag):
                    seen = [order.index(c.tag[len(w):]) for c in element
                            if c.tag.startswith(w) and c.tag[len(w):] in order]
                    assert seen == sorted(seen), f"{part}: {tag} children out of order"
        settings = [c.tag[len(w):] for c in etree.fromstring(package.read("word/settings.xml"))]
        assert settings.index("view") < settings.index("zoom") < settings.index("embedTrueTypeFonts")

        fonts = etree.fromstring(package.read("word/fontTable.xml"))
        embed = fonts.find(f".//{w}embedRegular")
        assert embed is not None
        key = embed.get(f"{w}fontKey")
        guid = bytes.fromhex(key.strip("{}").replace("-", ""))[::-1]
        data = package.read("word/fonts/fontRegular.odttf")
        restored = bytes(data[i] ^ guid[i % 16] for i in range(32)) + data[32:]
        assert restored[:4] == b"\x00\x01\x00\x00"

    doc = docx.Document(str(out_file))
    arabic = next(p for p in doc.paragraphs if "العقد" in p.text)
    size_cs = doc.styles["Normal"].element.rPr.find(f"{w}szCs")
    assert size_cs is not None and int(size_cs.get(f"{w}val")) == 40  # 20 pt in half-points
    assert arabic.paragraph_format.alignment is not None
    quote = next(p for p in doc.paragraphs if "Quoted judgment" in p.text)
    assert quote.style.name == "Quote"
    assert any(p.text == "جدول" and p.style.name == "Caption" for p in doc.paragraphs)
