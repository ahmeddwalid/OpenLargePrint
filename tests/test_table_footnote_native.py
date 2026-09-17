"""Tests for native PDF Table, Footnote, and Caption extraction (TBL-001, FN-001, FN-002)."""

from pathlib import Path
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import BlockType
from openlargeprint.security.isolation import JobWorkspace


def create_native_table_footnote_pdf(pdf_path: Path):
    """Create a native PDF containing a heading, a 3x3 table, a caption, and a footnote."""
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    # Page height is 792 pt, width is 612 pt

    # 1. Main Heading
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 730, "Legal Precedent Reference Guide")

    # 2. Body Paragraph
    c.setFont("Helvetica", 11)
    c.drawString(72, 700, "The following table summarizes key appellate precedents in negligence law.")

    # 3. Table Caption
    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, 665, "Table 1: Landmark Negligence Decisions")

    # 4. Table (3 columns: x=72, x=240, x=420; 3 rows: y=630, y=600, y=570)
    # Row 0: Header
    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, 630, "Case Name")
    c.drawString(240, 630, "Year")
    c.drawString(420, 630, "Jurisdiction")

    # Row 1: Data
    c.setFont("Helvetica", 10)
    c.drawString(72, 600, "Donoghue v Stevenson")
    c.drawString(240, 600, "1932")
    c.drawString(420, 600, "House of Lords")

    # Row 2: Data
    c.setFont("Helvetica", 10)
    c.drawString(72, 570, "Caparo Industries v Dickman")
    c.drawString(240, 570, "1990")
    c.drawString(420, 570, "House of Lords")

    # 5. Body paragraph below table
    c.drawString(72, 520, "Subsequent authorities refined the tripartite test established in Caparo.")

    # 6. Footnote at page bottom (y=80 <= 0.28 * 792 = 221.76 pt, font=8pt)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(72, 80, "1 Donoghue v Stevenson [1932] AC 562; established modern duty of care.")
    c.drawString(72, 65, "2 Caparo Industries plc v Dickman [1990] 2 AC 605; tripartite test.")

    c.showPage()
    c.save()


def test_native_table_and_footnote_extraction(tmp_path: Path):
    """Verify that NativePdfImporter extracts TableStructure, Footnotes, and Captions accurately."""
    pdf_path = tmp_path / "table_footnote.pdf"
    create_native_table_footnote_pdf(pdf_path)

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc = importer.import_document(pdf_path, ws)

    assert doc.metadata.page_count == 1
    blocks = doc.blocks

    # 1. Verify Table block (TBL-001)
    table_blocks = [b for b in blocks if b.type == BlockType.TABLE]
    assert len(table_blocks) >= 1, "A semantic TABLE block must be extracted"
    tbl = table_blocks[0]
    assert tbl.table_structure is not None
    assert tbl.table_structure.has_header is True
    assert tbl.table_structure.row_count >= 3
    assert tbl.table_structure.column_count == 3
    assert tbl.table_structure.rows[0][0].text == "Case Name"
    assert "Donoghue v Stevenson" in tbl.table_structure.rows[1][0].text

    # 2. Verify Footnote blocks (FN-001)
    footnote_blocks = [b for b in blocks if b.type == BlockType.FOOTNOTE]
    assert len(footnote_blocks) >= 1, "Footnote blocks must be extracted"
    fn_text = " ".join(b.text or "" for b in footnote_blocks)
    assert "Donoghue v Stevenson" in fn_text or "1" in fn_text
    assert "Caparo" in fn_text

    # 3. Verify Caption block
    caption_blocks = [b for b in blocks if b.type == BlockType.CAPTION]
    assert len(caption_blocks) >= 1, "Caption block must be extracted"
    assert "Table 1:" in caption_blocks[0].text
