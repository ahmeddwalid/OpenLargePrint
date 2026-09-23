"""Regression tests for image retention, configured text size, and layout fidelity.

Covers the fixes for IMG-001/002/003, OUT-002/004/006/009, TBL-001, DOC-002.
"""

from pathlib import Path

import docx
import pikepdf
import pypdfium2 as pdfium
import pytest
from docx.shared import Pt
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.exporters import ExportOptions, PaperSize, PdfExporter, PresetName, ReaderExporter
from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    PageClassification,
    PageMetadata,
)
from openlargeprint.ir.serialization import document_to_ui_dict
from openlargeprint.pipeline import PipelineOrchestrator
from openlargeprint.security import JobAssetStore


def _write_image(path: Path, size=(300, 150)) -> None:
    Image.new("RGB", size, color=(120, 160, 200)).save(path)


# --- Image retention (IMG-001) -------------------------------------------------

def test_images_persist_after_conversion(tmp_path: Path):
    """Extracted media must remain readable after the disposable workspace is torn down."""
    img_path = tmp_path / "figure.png"
    _write_image(img_path)
    pdf_path = tmp_path / "with_image.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 700, "Figure Description Above")
    c.drawImage(str(img_path), 72, 500, width=250, height=125)
    c.showPage()
    c.save()

    store = JobAssetStore(job_id="fidelity-images", root=tmp_path / "cache")
    orchestrator = PipelineOrchestrator()
    result = orchestrator.convert(
        pdf_path, tmp_path / "out.docx", ExportOptions(), asset_store=store
    )

    image_blocks = [b for b in result.document_ir.blocks if b.type == BlockType.IMAGE]
    assert image_blocks, "the embedded figure must be retained"
    for block in image_blocks:
        assert block.image_asset is not None
        assert block.image_asset.file_path is not None
        assert Path(block.image_asset.file_path).exists(), "image asset must survive workspace teardown"

    assert result.asset_root is not None
    assert str(result.asset_root) in str(image_blocks[0].image_asset.file_path)


def test_ui_dict_embeds_image_data_url(tmp_path: Path):
    """The desktop UI payload must carry a renderable data URL for figures."""
    img_path = tmp_path / "figure.png"
    _write_image(img_path)
    pdf_path = tmp_path / "with_image.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawImage(str(img_path), 72, 500, width=250, height=125)
    c.showPage()
    c.save()

    store = JobAssetStore(job_id="fidelity-ui", root=tmp_path / "cache")
    result = PipelineOrchestrator().convert(
        pdf_path, tmp_path / "out.docx", ExportOptions(), asset_store=store
    )
    ui = document_to_ui_dict(result.document_ir)
    image_blocks = [b for b in ui["blocks"] if b["type"] == "image"]
    assert image_blocks
    assert image_blocks[0]["image_asset"]["data_url"].startswith("data:image/")


@pytest.mark.parametrize("path_count", [1, 12])
def test_vector_figure_region_retained(tmp_path: Path, path_count: int):
    """A page with vector artwork but no embedded raster still keeps the figure (IMG-002)."""
    pdf_path = tmp_path / "vector.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    for i in range(path_count):
        c.rect(100 + i * 10, 400 + i * 8, 200, 120, stroke=1, fill=0)
    c.setFont("Helvetica", 10)
    c.drawString(50, 60, "Vector figure above.")
    c.showPage()
    c.save()

    result = PipelineOrchestrator().convert(pdf_path, tmp_path / "out.docx", ExportOptions())
    image_blocks = [b for b in result.document_ir.blocks if b.type == BlockType.IMAGE]
    assert image_blocks, "vector artwork must be preserved via region rendering"


def test_text_page_has_no_false_positive_figures(tmp_path: Path):
    """Ordinary text pages must not gain spurious vector-figure blocks."""
    pdf_path = tmp_path / "text_only.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 11)
    for i in range(30):
        c.drawString(60, 750 - i * 20, f"Ordinary body text line {i} with no figures at all.")
    c.showPage()
    c.save()

    result = PipelineOrchestrator().convert(pdf_path, tmp_path / "out.docx", ExportOptions())
    assert [b for b in result.document_ir.blocks if b.type == BlockType.IMAGE] == []


# --- Configured text size (OUT-002/006/009) ------------------------------------

def test_docx_honors_custom_body_size(tmp_path: Path):
    """A custom point size must reach the exported DOCX, not just the preset table."""
    pdf_path = tmp_path / "body.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 11)
    c.drawString(72, 700, "Custom sized body paragraph for the reader.")
    c.showPage()
    c.save()

    out = tmp_path / "custom.docx"
    PipelineOrchestrator().convert(
        pdf_path,
        out,
        ExportOptions(preset=PresetName.CUSTOM, custom_body_pt=30.0, custom_line_spacing=1.7),
    )
    doc = docx.Document(str(out))
    body = next(p for p in doc.paragraphs if "Custom sized body" in p.text)
    assert body.runs[0].font.size == Pt(30)
    assert body.paragraph_format.line_spacing == 1.7


def test_reader_html_uses_points_and_has_width_control(tmp_path: Path):
    """The HTML Reader must express size in pt (not px) and expose a reading-width control."""
    ir = DocumentIR(
        metadata=DocumentMetadata(title="Reader", page_count=1),
        pages=[PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)],
        blocks=[Block(id="p1_p", type=BlockType.PARAGRAPH, text="Reader body text.", source_page=1)],
    )
    out = tmp_path / "reader.html"
    ReaderExporter().export(ir, out, ExportOptions(preset=PresetName.LARGE))
    html = out.read_text(encoding="utf-8")

    assert "--base-font-size: 20pt" in html
    assert "--base-font-size: 20px" not in html
    assert 'id="reading-width-select"' in html
    assert 'id="current-size-label"' in html


# --- Layout fidelity (TBL-001, OUT-009) ----------------------------------------

def test_pdf_list_renders_real_bullet(tmp_path: Path):
    """PDF list items must render a bullet, never a literal HTML entity."""
    ir = DocumentIR(
        metadata=DocumentMetadata(title="Lists", page_count=1),
        pages=[PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)],
        blocks=[Block(id="p1_l", type=BlockType.LIST, text="First bullet point", source_page=1)],
    )
    out = tmp_path / "list.pdf"
    PdfExporter().export(ir, out, ExportOptions())

    page = pdfium.PdfDocument(out)[0]
    text = page.get_textpage().get_text_range()
    assert "First bullet point" in text
    assert "&nbsp;" not in text
    assert "&amp;nbsp;" not in text


def test_pdf_tall_image_is_height_clamped(tmp_path: Path):
    """A very tall figure must be scaled down to fit the page without distortion."""
    tall = tmp_path / "tall.png"
    Image.new("RGB", (200, 4000), color=(10, 10, 10)).save(tall)

    from openlargeprint.ir.models import ImageAsset

    ir = DocumentIR(
        metadata=DocumentMetadata(title="Tall", page_count=1),
        pages=[PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)],
        blocks=[
            Block(
                id="p1_img",
                type=BlockType.IMAGE,
                source_page=1,
                image_asset=ImageAsset(asset_id="a", file_path=str(tall), width=200, height=4000),
            )
        ],
    )
    out = tmp_path / "tall.pdf"
    PdfExporter().export(ir, out, ExportOptions(paper_size=PaperSize.A4))

    # The page must still be A4 and the document must be exactly one page
    # (an unclamped image would overflow onto additional pages).
    pdf = pdfium.PdfDocument(out)
    assert len(pdf) == 1


def test_docx_table_body_rows_can_split(tmp_path: Path):
    """Only the header row should be marked cantSplit; body rows must be able to break."""
    from openlargeprint.ir.models import TableCell, TableStructure

    table = TableStructure(
        rows=[[TableCell(text="H1"), TableCell(text="H2")], [TableCell(text="a"), TableCell(text="b")]],
        has_header=True,
    )
    ir = DocumentIR(
        metadata=DocumentMetadata(title="Table", page_count=1),
        pages=[PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)],
        blocks=[Block(id="p1_t", type=BlockType.TABLE, text="t", source_page=1, table_structure=table)],
    )
    out = tmp_path / "table.docx"
    from openlargeprint.exporters import DocxExporter

    DocxExporter().export(ir, out, ExportOptions())
    xml = docx.Document(str(out))._element.xml
    # Two rows total, but only the header row carries cantSplit.
    assert xml.count("cantSplit") == 1


# --- Searchable PDF (OUT-004) --------------------------------------------------

def test_searchable_pdf_preserves_layout_and_adds_text(tmp_path: Path):
    """Searchable export must keep the original page size and embed a text layer."""
    pdf_path = tmp_path / "native.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "Searchable contract clause 7.2")
    c.showPage()
    c.save()

    out = tmp_path / "searchable.pdf"
    result = PipelineOrchestrator().convert(
        pdf_path, out, ExportOptions(), export_format="searchable_pdf"
    )
    assert result.format == "searchable_pdf"
    assert out.exists()

    page = pdfium.PdfDocument(out)[0]
    w, h = page.get_size()
    assert pytest.approx(w, 1.0) == 612.0
    assert pytest.approx(h, 1.0) == 792.0
    assert "clause 7.2" in page.get_textpage().get_text_range()


def test_searchable_pdf_succeeds_on_blank_or_textless_pages(tmp_path: Path):
    """Searchable export must not crash when a document contains a blank or textless page (OUT-004, SPEC §2)."""
    pdf_path = tmp_path / "with_blank.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "Page 1 heading")
    c.showPage()
    # Page 2: intentionally blank
    c.showPage()
    # Page 3: more text
    c.drawString(72, 700, "Page 3 body")
    c.showPage()
    c.save()

    out = tmp_path / "searchable_with_blank.pdf"
    result = PipelineOrchestrator().convert(
        pdf_path, out, ExportOptions(), export_format="searchable_pdf"
    )
    assert result.format == "searchable_pdf"
    assert out.exists()

    with pdfium.PdfDocument(out) as doc:
        assert len(doc) == 3
        assert "Page 1 heading" in doc[0].get_textpage().get_text_range()
        assert "Page 3 body" in doc[2].get_textpage().get_text_range()


def test_searchable_pdf_overlays_text_on_scanned_page(tmp_path: Path):
    """Searchable export must successfully overlay text onto a scanned/raster-only page (OUT-004)."""
    from PIL import Image, ImageDraw

    # Create a scanned-like image with text rendered as pixels
    img = Image.new("RGB", (600, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 50), "Scanned clause 9.4", fill="black")
    img_path = tmp_path / "page_raster.png"
    img.save(img_path)

    # Put this raster image into a PDF without native text
    pdf_path = tmp_path / "scanned_doc.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=(600, 200))
    c.drawImage(str(img_path), 0, 0, width=600, height=200)
    c.showPage()
    c.save()

    out = tmp_path / "searchable_scanned.pdf"
    result = PipelineOrchestrator().convert(
        pdf_path, out, ExportOptions(), export_format="searchable_pdf"
    )
    assert result.format == "searchable_pdf"
    assert out.exists()

    with pdfium.PdfDocument(out) as doc:
        assert len(doc) == 1
        text = doc[0].get_textpage().get_text_range()
        assert "clause" in text.lower() or "scanned" in text.lower()


def test_docx_section_break_advances_page(tmp_path: Path):
    """A Word section break must produce a new source page (OFF-001, PDF-006)."""
    from docx.enum.section import WD_SECTION

    from openlargeprint.importers.office.docx import DocxImporter
    from openlargeprint.security import JobWorkspace

    docx_path = tmp_path / "sections.docx"
    document = docx.Document()
    document.add_paragraph("Page one content.")
    document.add_section(WD_SECTION.NEW_PAGE)
    document.add_paragraph("Page two content.")
    document.save(str(docx_path))

    with JobWorkspace() as ws:
        ir = DocxImporter().import_document(docx_path, ws)

    assert ir.metadata.page_count == 2
    markers = [b.page_marker for b in ir.blocks if b.type == BlockType.PAGE_MARKER]
    assert markers == [1, 2]


def test_searchable_pdf_rejects_non_pdf(tmp_path: Path):
    """Searchable original export only applies to PDF input."""
    docx_path = tmp_path / "doc.docx"
    d = docx.Document()
    d.add_paragraph("hello")
    d.save(str(docx_path))

    with pytest.raises(ValueError):
        PipelineOrchestrator().convert(
            docx_path, tmp_path / "out.pdf", ExportOptions(), export_format="searchable_pdf"
        )


def test_searchable_native_pdf_retains_vector_content(tmp_path: Path):
    source = tmp_path / "vector-source.pdf"
    c = canvas.Canvas(str(source), pagesize=letter)
    c.drawString(72, 700, "Keep exact native text")
    c.rect(72, 400, 160, 120)
    c.showPage()
    c.save()
    output = tmp_path / "searchable-vector.pdf"
    PipelineOrchestrator().convert(source, output, export_format="searchable_pdf")
    with pikepdf.open(source) as before, pikepdf.open(output) as after:
        assert before.pages[0].Contents.read_bytes() == after.pages[0].Contents.read_bytes()
        assert not after.pages[0].get_images()


def test_searchable_selection_preserves_original_sizes(tmp_path: Path):
    source = tmp_path / "mixed-sizes.pdf"
    c = canvas.Canvas(str(source))
    for index, size in enumerate(((200, 300), (842, 1191), (612, 792))):
        c.setPageSize(size)
        c.drawString(20, 100, f"Selected source page {index + 1}")
        c.showPage()
    c.save()
    output = tmp_path / "selection.pdf"
    result = PipelineOrchestrator().convert(source, output, export_format="searchable_pdf", page_range=[2])
    with pdfium.PdfDocument(output) as pdf:
        assert len(pdf) == 1
        assert pdf[0].get_size() == (842, 1191)
    assert [p.page_number for p in result.document_ir.pages] == [2]


def test_failed_extraction_preserves_real_page_image(tmp_path: Path, monkeypatch):
    source = tmp_path / "failed-extraction.pdf"
    c = canvas.Canvas(str(source), pagesize=letter)
    c.drawString(72, 700, "Original content must remain available")
    c.showPage()
    c.save()
    orchestrator = PipelineOrchestrator()
    def fail(*args, **kwargs):
        raise RuntimeError("extraction failed")
    monkeypatch.setattr(orchestrator.pdf_importer, "_extract_native_text", fail)
    store = JobAssetStore(job_id="failure-retention", root=tmp_path / "cache")
    result = orchestrator.convert(source, tmp_path / "retained.docx", asset_store=store)
    retained = [b for b in result.document_ir.blocks if b.image_asset]
    assert retained
    assert Path(retained[0].image_asset.file_path).is_file()
    assert result.warnings
def test_every_source_page_keeps_its_anchor(tmp_path: Path):
    """No source page may be dropped during conversion (SPEC 2, PDF-006, OUT-005)."""
    src = tmp_path / "six_pages.pdf"
    c = canvas.Canvas(str(src), pagesize=letter)
    for i in range(6):
        c.setFont("Helvetica", 12)
        c.drawString(60, 700, f"Article {i + 1}. This clause survives reflow.")
        c.showPage()
    c.save()

    result = PipelineOrchestrator().convert(src, tmp_path / "six_pages_out.docx")

    source_pages = {p.page_number for p in result.document_ir.pages}
    marked_pages = {b.page_marker for b in result.document_ir.blocks if b.type == BlockType.PAGE_MARKER}

    assert result.success is True
    assert source_pages == {1, 2, 3, 4, 5, 6}
    assert source_pages <= marked_pages, f"pages without an anchor: {sorted(source_pages - marked_pages)}"


def test_cropbox_filters_bleed_and_normalizes_coordinates(tmp_path: Path):
    """CropBox must exclude bleed/registration marks and normalize coordinates to 0-based page (PDF-001..007)."""
    src = tmp_path / "cropbox_test.pdf"
    c = canvas.Canvas(str(src), pagesize=(1000, 1000))
    # Bleed text outside cropbox (x < 500)
    c.setFont("Helvetica", 10)
    c.drawString(100, 500, "PRINTER COLOR BAR / REGISTRATION MARK")
    # Content text inside cropbox (x=600, y=500)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(600, 500, "Visible Chapter Content Inside CropBox")
    c.showPage()
    c.save()

    # Set CropBox to (500, 100, 900, 800) using pikepdf
    with pikepdf.open(src, allow_overwriting_input=True) as pike:
        pike.pages[0].CropBox = pikepdf.Array([500, 100, 900, 800])
        pike.save(src)

    from openlargeprint.importers.pdf.native import NativePdfImporter
    from openlargeprint.security.isolation import JobWorkspace

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        ir = importer.import_document(src, ws)

    # 1. Bleed text must be completely omitted
    all_text = " ".join(b.text or "" for b in ir.blocks)
    assert "PRINTER COLOR BAR" not in all_text
    assert "Visible Chapter Content" in all_text

    # 2. Coordinates of content block must be normalized relative to CropBox (x ~ 100, not x ~ 600)
    content_blocks = [b for b in ir.blocks if b.type != BlockType.PAGE_MARKER and b.text and "Visible Chapter" in b.text]
    assert content_blocks
    cb_box = content_blocks[0].source_bounding_box
    assert cb_box is not None
    # 600 - 500 = 100
    assert 90.0 <= cb_box.x0 <= 110.0, f"Expected normalized x0 near 100, got {cb_box.x0}"


def test_font_proportional_spacing_preserves_large_titles():
    """Font-proportional spacing must prevent split words in titles while separating real words."""
    from openlargeprint.importers.pdf.native import NativePdfImporter, TextLine

    importer = NativePdfImporter()
    # 72pt font: normal kerning between 'GR' and 'AMMAR' is ~3.5pt (< 0.22 * 72 = 15.8pt)
    frags = [
        TextLine(text="GR", rect=(50.0, 500.0, 120.0, 570.0), font_size=72.0, font_name="Helvetica-Bold", is_bold=True, page_num=1),
        TextLine(text="AMMAR", rect=(123.5, 500.0, 300.0, 570.0), font_size=72.0, font_name="Helvetica-Bold", is_bold=True, page_num=1),
        # Distinct word separated by 25pt gap (> 15.8pt)
        TextLine(text="BOOK", rect=(325.0, 500.0, 450.0, 570.0), font_size=72.0, font_name="Helvetica-Bold", is_bold=True, page_num=1),
    ]

    lines = importer._aggregate_fragments_into_lines(frags, 1)
    assert len(lines) == 1
    assert lines[0].text == "GRAMMAR BOOK"


def test_numbered_outlines_do_not_render_bullets_in_exporters(tmp_path: Path):
    """Numbered outlines and TOC entries must retain clean numbering without prepended bullet symbols."""
    ir = DocumentIR(
        metadata=DocumentMetadata(title="Outline Test", page_count=1),
        pages=[PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE)],
        blocks=[
            Block(id="p1_l1", type=BlockType.LIST, text="1. Present continuous (I am doing)", source_page=1),
            Block(id="p1_l2", type=BlockType.LIST, text="• Regular bulleted item", source_page=1),
        ],
    )

    pdf_out = tmp_path / "out.pdf"
    PdfExporter().export(ir, pdf_out, ExportOptions())
    page = pdfium.PdfDocument(pdf_out)[0]
    pdf_text = page.get_textpage().get_text_range()

    # Numbered item must NOT have prepended bullet
    assert "•  1." not in pdf_text and "• 1." not in pdf_text
    assert "1. Present continuous" in pdf_text

    # Bulleted item must have bullet
    assert "•  Regular bulleted item" in pdf_text or "• Regular bulleted item" in pdf_text

    # DOCX export check
    docx_out = tmp_path / "out.docx"
    from openlargeprint.exporters import DocxExporter
    DocxExporter().export(ir, docx_out, ExportOptions())
    doc = docx.Document(docx_out)
    paragraphs = [p for p in doc.paragraphs if p.text]
    p1 = [p for p in paragraphs if "Present continuous" in p.text][0]
    p2 = [p for p in paragraphs if "Regular bulleted" in p.text][0]
    assert p1.style.name != "List Bullet", "Numbered outline must not use List Bullet style"
    assert p2.style.name == "List Bullet", "Bulleted item should use List Bullet style"

    # HTML Reader check
    html_out = tmp_path / "out.html"
    ReaderExporter().export(ir, html_out, ExportOptions())
    html_content = html_out.read_text(encoding="utf-8")
    assert '<p class="list-item list-numbered">1. Present continuous' in html_content
    assert '<ul><li>Regular bulleted item</li></ul>' in html_content

