"""End-to-end integration test proving Milestone 1 hypothesis:
Healthy digital PDF -> exact extraction & images -> DocumentIR -> 20pt DOCX.
"""

from pathlib import Path
from PIL import Image
import docx
from docx.shared import Pt
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.exporters import ExportOptions, PaperSize, PresetName
from openlargeprint.ir.models import BlockType, PageClassification
from openlargeprint.pipeline import PipelineOrchestrator


def generate_benchmark_law_pdf(pdf_path: Path, img_path: Path):
    """Generate a representative two-column law text PDF with headings, lists, footnotes, and an image."""
    # 1. Create figure image
    img = Image.new("RGB", (250, 100), color=(180, 200, 220))
    img.save(img_path)

    c = canvas.Canvas(str(pdf_path), pagesize=letter)

    # PAGE 1: Two-column law chapter
    # Full-width Chapter title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, 720, "Chapter 4: Principles of Administrative Law")

    # Column 1 (x=50, max width ~ 230 pt, right margin ~ 280 pt)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, 680, "1. Scope of Judicial Review")
    c.setFont("Helvetica", 10)
    c.drawString(50, 660, "Administrative bodies derive authority")
    c.drawString(50, 645, "strictly from enabling statutes.")
    c.drawString(50, 625, "Ultra vires acts remain null and void")
    c.drawString(50, 610, "ab initio without legal force.")
    c.drawString(50, 580, "• Error of law on the face of the record")
    c.drawString(50, 565, "• Breach of natural justice principles")

    # Figure embedded in Column 1
    c.drawImage(str(img_path), 50, 460, width=200, height=80)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 445, "Figure 4.1: Hierarchy of Statutory Review.")

    # Column 2 (x=320, max width ~ 230 pt, right margin ~ 550 pt)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(320, 680, "2. Procedural Fairness Requirements")
    c.setFont("Helvetica", 10)
    c.drawString(320, 660, "The right to a fair hearing encompasses")
    c.drawString(320, 645, "adequate notice of allegations.")
    c.drawString(320, 625, "Affected parties must be afforded a")
    c.drawString(320, 610, "meaningful opportunity to respond.")

    # Page 1 Footnote across bottom
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 60, "1. See Ridge v Baldwin [1964] AC 40 for the modern formulation.")
    c.showPage()

    # PAGE 2: Continuation
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 720, "3. Substantive Legitimate Expectations")
    c.setFont("Helvetica", 10)
    c.drawString(50, 690, "Where an authority makes an unambiguous representation devoid of qualification,")
    c.drawString(50, 675, "the court may enforce the expectation absent compelling public interest.")
    c.showPage()

    c.save()


def test_milestone1_end_to_end_conversion(tmp_path: Path):
    """Execute complete Milestone 1 vertical slice:
    Digital PDF -> Native text & image extraction -> DocumentIR -> 20pt DOCX.
    """
    pdf_file = tmp_path / "admin_law.pdf"
    img_file = tmp_path / "diagram.png"
    out_docx = tmp_path / "admin_law_large_print.docx"

    generate_benchmark_law_pdf(pdf_file, img_file)

    orchestrator = PipelineOrchestrator()
    options = ExportOptions(
        preset=PresetName.LARGE,  # 20pt / 1.5 line spacing (OUT-006)
        paper_size=PaperSize.A4,   # A4 default (OUT-007)
        include_page_markers=True, # Original page markers (OUT-005)
    )

    result = orchestrator.convert(pdf_file, out_docx, options)

    # 1. Pipeline execution assertions
    assert result.success is True
    assert out_docx.exists()
    assert out_docx.stat().st_size > 0

    doc_ir = result.document_ir

    # 2. Canonical DocumentIR assertions (DOC-001..003)
    assert doc_ir.schema_version == "1.0.0"
    assert doc_ir.metadata.page_count == 2
    assert len(doc_ir.pages) == 2
    assert all(p.classification == PageClassification.NATIVE for p in doc_ir.pages)

    # Verify blocks retain source provenance (PDF-006)
    for block in doc_ir.blocks:
        assert block.source_page in (1, 2)
        if block.type != BlockType.PAGE_MARKER:
            assert block.source_bounding_box is not None

    # Verify column reading order: Column 1 text precedes Column 2 text
    texts = [b.text for b in doc_ir.blocks if b.text]
    sec1_pos = next(i for i, t in enumerate(texts) if "Scope of Judicial Review" in t)
    col1_body_pos = next(i for i, t in enumerate(texts) if "statutes" in t)
    sec2_pos = next(i for i, t in enumerate(texts) if "Procedural Fairness" in t)
    col2_body_pos = next(i for i, t in enumerate(texts) if "fair hearing" in t)

    assert sec1_pos < col1_body_pos < sec2_pos < col2_body_pos

    # Verify image was extracted into an IMAGE block
    img_blocks = [b for b in doc_ir.blocks if b.type == BlockType.IMAGE]
    assert len(img_blocks) == 1
    assert img_blocks[0].image_asset is not None
    assert img_blocks[0].image_asset.width == 250

    # 3. Large-Print DOCX file assertions (OUT-001, OUT-005..009)
    doc = docx.Document(str(out_docx))
    section = doc.sections[0]

    # Verify A4 dimensions (OUT-007, OUT-009)
    assert pytest.approx(section.page_width.mm, 1.0) == 210.0
    assert pytest.approx(section.page_height.mm, 1.0) == 297.0

    # Verify print reminder in metadata (OUT-009)
    assert "Print at 100%" in doc.core_properties.comments

    paragraphs = doc.paragraphs

    # Verify page markers are present (OUT-005)
    page1_marker = next(p for p in paragraphs if "Original Page 1" in p.text)
    page2_marker = next(p for p in paragraphs if "Original Page 2" in p.text)
    assert page1_marker is not None
    assert page2_marker is not None

    # Verify Title / Heading 1 typography (OUT-001)
    title_para = next(p for p in paragraphs if "Principles of Administrative Law" in p.text)
    assert title_para.runs[0].font.bold is True
    # H1 is 28pt for 20pt body
    assert title_para.runs[0].font.size == Pt(28)

    # Verify body typography: 20pt body, 1.5 line spacing (OUT-006)
    body_para = next(p for p in paragraphs if "Ultra vires" in p.text)
    assert body_para.runs[0].font.size == Pt(20)
    assert body_para.paragraph_format.line_spacing == 1.5

    # Verify inline images (embedded picture element in document)
    xml = doc._element.xml
    assert "drawing" in xml or "blip" in xml


def test_pipeline_inspect_and_custom_options(tmp_path: Path):
    """Verify inspect() API and custom export options."""
    pdf_file = tmp_path / "inspect_test.pdf"
    img_file = tmp_path / "inspect_img.png"
    generate_benchmark_law_pdf(pdf_file, img_file)

    orch = PipelineOrchestrator()
    doc_ir = orch.inspect(pdf_file)
    assert doc_ir.metadata.page_count == 2
    assert len(doc_ir.blocks) > 0

    # Custom options
    custom_opts = ExportOptions(
        preset=PresetName.CUSTOM,
        custom_body_pt=22.0,
        custom_line_spacing=1.6,
    )
    assert custom_opts.body_pt == 22.0
    assert custom_opts.line_spacing == 1.6
