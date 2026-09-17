"""End-to-end integration tests for Milestone 5: Complex Structures (TBL-001, TBL-002, FN-001, FN-002)."""

from pathlib import Path
import docx
from docx.oxml.ns import qn
import pypdfium2 as pdfium
import pytest

from openlargeprint.exporters.base import ExportOptions, PaperSize, PresetName
from openlargeprint.exporters.docx import DocxExporter
from openlargeprint.exporters.pdf import PdfExporter
from openlargeprint.exporters.reader import ReaderExporter
from openlargeprint.ir.models import (
    Block,
    BlockType,
    BoundingBox,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    PageClassification,
    PageMetadata,
    TableCell,
    TableStructure,
    TextDirection,
)


def create_milestone5_ir() -> DocumentIR:
    """Construct DocumentIR with semantic tables, RTL tables, footnotes, and captions."""
    metadata = DocumentMetadata(
        title="Complex Structures Legal Analysis",
        source_file_name="legal_complex.pdf",
        page_count=1,
    )
    pages = [
        PageMetadata(
            page_number=1,
            width=612.0,
            height=792.0,
            classification=PageClassification.NATIVE,
        )
    ]

    # 1. Standard LTR Table
    table_ltr = TableStructure(
        has_header=True,
        caption="Key Appellate Precedents",
        rows=[
            [
                TableCell(text="Case Name", is_header=True),
                TableCell(text="Year", is_header=True),
                TableCell(text="Jurisdiction", is_header=True),
            ],
            [
                TableCell(text="Donoghue v Stevenson"),
                TableCell(text="1932"),
                TableCell(text="House of Lords"),
            ],
            [
                TableCell(text="Hedley Byrne v Heller"),
                TableCell(text="1964"),
                TableCell(text="House of Lords"),
            ],
        ],
    )

    # 2. Arabic RTL Table (LANG-001)
    table_rtl = TableStructure(
        has_header=True,
        caption="أركان المسؤولية التقصيرية",
        rows=[
            [
                TableCell(text="الركن", is_header=True),
                TableCell(text="التعريف القانوني", is_header=True),
                TableCell(text="الأساس القضائي", is_header=True),
            ],
            [
                TableCell(text="الخطأ"),
                TableCell(text="الإخلال بواجب قانوني عام"),
                TableCell(text="المادة ١٦٣ من القانون المدني"),
            ],
            [
                TableCell(text="الضرر"),
                TableCell(text="الأذى المالي أو المعنوي"),
                TableCell(text="الضرر المباشر المتوقع"),
            ],
        ],
    )

    # 3. Dense 6-Column Table with warning (TBL-002)
    table_wide = TableStructure(
        has_header=True,
        caption="Statutory Limitation Periods Across Commonwealth Jurisdictions",
        rows=[
            [
                TableCell(text="Jurisdiction", is_header=True),
                TableCell(text="Tort (General)", is_header=True),
                TableCell(text="Contractual Breach", is_header=True),
                TableCell(text="Personal Injury", is_header=True),
                TableCell(text="Defamation", is_header=True),
                TableCell(text="Judicial Review", is_header=True),
            ],
            [
                TableCell(text="England & Wales"),
                TableCell(text="6 years"),
                TableCell(text="6 years"),
                TableCell(text="3 years"),
                TableCell(text="1 year"),
                TableCell(text="3 months"),
            ],
            [
                TableCell(text="Australia (NSW)"),
                TableCell(text="6 years"),
                TableCell(text="6 years"),
                TableCell(text="3 years"),
                TableCell(text="1 year"),
                TableCell(text="28 days"),
            ],
        ],
    )

    blocks = [
        Block(
            id="p1_m",
            type=BlockType.PAGE_MARKER,
            page_marker=1,
            source_page=1,
        ),
        Block(
            id="p1_h1",
            type=BlockType.HEADING,
            text="Comparative Torts & Statutory Limitations",
            level=1,
            source_page=1,
        ),
        Block(
            id="p1_p1",
            type=BlockType.PARAGRAPH,
            text="The doctrine of negligence relies upon clearly delineated duties of care.",
            source_page=1,
        ),
        Block(
            id="p1_cap1",
            type=BlockType.CAPTION,
            text="Table 1: Landmark Negligence Decisions in Common Law",
            source_page=1,
        ),
        Block(
            id="p1_tbl1",
            type=BlockType.TABLE,
            text=table_ltr.to_markdown_table(),
            table_structure=table_ltr,
            source_page=1,
            source_bounding_box=BoundingBox(x0=72, y0=500, x1=540, y1=620),
        ),
        Block(
            id="p1_tbl2",
            type=BlockType.TABLE,
            text=table_rtl.to_markdown_table(),
            table_structure=table_rtl,
            language="ar",
            text_direction=TextDirection.RTL,
            source_page=1,
            source_bounding_box=BoundingBox(x0=72, y0=350, x1=540, y1=470),
        ),
        Block(
            id="p1_tbl3",
            type=BlockType.TABLE,
            text=table_wide.to_markdown_table(),
            table_structure=table_wide,
            warnings=["Table with 6 columns requires layout adaptation (TBL-001)"],
            source_page=1,
            source_bounding_box=BoundingBox(x0=72, y0=200, x1=540, y1=320),
        ),
        Block(
            id="p1_fn1",
            type=BlockType.FOOTNOTE,
            text="1 Donoghue v Stevenson [1932] AC 562; established the neighbour principle.",
            source_page=1,
        ),
        Block(
            id="p1_fn2",
            type=BlockType.FOOTNOTE,
            text="٢ تنص المادة ١٦٣ على أن كل خطأ سبب ضرراً للغير يلزم من ارتكبه بالتعويض.",
            language="ar",
            text_direction=TextDirection.RTL,
            source_page=1,
        ),
    ]

    return DocumentIR(
        schema_version="1.0.0",
        metadata=metadata,
        pages=pages,
        blocks=blocks,
    )


def test_milestone5_docx_export(tmp_path: Path):
    """Verify DOCX exporter produces styled tables, bidiVisual for RTL, and legible footnotes (TBL-001, FN-002)."""
    doc_ir = create_milestone5_ir()
    docx_path = tmp_path / "milestone5_output.docx"

    exporter = DocxExporter()
    options = ExportOptions(preset=PresetName.COMFORTABLE, paper_size=PaperSize.A4)
    out_file = exporter.export(doc_ir, docx_path, options)

    assert out_file.exists()
    doc = docx.Document(docx_path)

    # 1. Verify tables are present in Word document
    assert len(doc.tables) >= 2, "DOCX must contain at least 2 structured tables"

    # 2. Verify Table 1 structure
    t1 = doc.tables[0]
    assert len(t1.rows) == 3
    assert len(t1.columns) == 3
    assert t1.rows[0].cells[0].text == "Case Name"
    assert "Donoghue v Stevenson" in t1.rows[1].cells[0].text

    # Verify header repeat and cantSplit XML elements
    trPr = t1.rows[0]._tr.get_or_add_trPr()
    assert trPr.find(qn("w:tblHeader")) is not None, "Header row must have tblHeader attribute"
    assert trPr.find(qn("w:cantSplit")) is not None, "Rows must have cantSplit attribute"

    # 3. Verify RTL Table 2 has w:bidiVisual (LANG-001)
    t2 = doc.tables[1]
    tblPr2 = t2._tbl.tblPr
    assert tblPr2.find(qn("w:bidiVisual")) is not None, "RTL table must have w:bidiVisual"

    # 4. Verify Footnote font size >= 14pt (FN-002)
    # Check all paragraphs looking for footnote text
    fn_paragraphs = [p for p in doc.paragraphs if "Donoghue v Stevenson [1932]" in p.text]
    assert len(fn_paragraphs) >= 1
    fn_p = fn_paragraphs[0]
    assert len(fn_p.runs) > 0
    fn_size = fn_p.runs[0].font.size.pt
    assert fn_size >= 14.0, f"Footnote size must be >= 14pt per FN-002, got {fn_size}pt"


def test_milestone5_pdf_export(tmp_path: Path):
    """Verify PDF exporter renders tables, captions, and footnotes at A4 size (TBL-001, FN-002, OUT-007)."""
    doc_ir = create_milestone5_ir()
    pdf_path = tmp_path / "milestone5_output.pdf"

    exporter = PdfExporter()
    options = ExportOptions(preset=PresetName.COMFORTABLE, paper_size=PaperSize.A4)
    out_file = exporter.export(doc_ir, pdf_path, options)

    assert out_file.exists()

    # Verify PDF with pdfium
    pdf_doc = pdfium.PdfDocument(pdf_path)
    assert len(pdf_doc) >= 1
    page = pdf_doc[0]
    # A4 dimensions in points: 595.27 x 841.89 (within 2pt tolerance)
    w, h = page.get_size()
    assert abs(w - 595.27) < 3.0
    assert abs(h - 841.89) < 3.0

    # Verify extracted text contains table content
    tp = page.get_textpage()
    full_text = tp.get_text_range()
    assert "Case Name" in full_text
    assert "Donoghue" in full_text
    assert "Table 1:" in full_text


def test_milestone5_reader_export(tmp_path: Path):
    """Verify Reader exporter produces accessible <table>, <aside>, <figcaption>, and warnings (TBL-001, TBL-002)."""
    doc_ir = create_milestone5_ir()
    html_path = tmp_path / "milestone5_reader.html"

    exporter = ReaderExporter()
    options = ExportOptions(preset=PresetName.COMFORTABLE)
    out_file = exporter.export(doc_ir, html_path, options)

    assert out_file.exists()
    html_content = html_path.read_text(encoding="utf-8")

    # 1. Semantic tables
    assert '<table class="large-print-table"' in html_content
    assert '<th scope="col">Case Name</th>' in html_content
    assert "<td>Donoghue v Stevenson</td>" in html_content
    assert "<caption>Key Appellate Precedents</caption>" in html_content

    # 2. RTL table dir
    assert 'class="large-print-table rtl" dir="rtl"' in html_content

    # 3. Visible warning banner (TBL-002)
    assert 'class="table-warning"' in html_content
    assert "Table with 6 columns" in html_content

    # 4. Captions
    assert '<figcaption class="caption-block"' in html_content
    assert "Table 1: Landmark Negligence Decisions" in html_content

    # 5. Footnotes with role="doc-footnote" (FN-001)
    assert '<aside class="footnote-block" role="doc-footnote">' in html_content
    assert "Donoghue v Stevenson [1932]" in html_content
    assert '<aside class="footnote-block rtl" dir="rtl" role="doc-footnote">' in html_content
