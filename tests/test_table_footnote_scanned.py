"""Tests for scanned PDF table and footnote extraction with crop retention (TBL-001, FN-001)."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.scanned import ScannedPageExtractor
from openlargeprint.ir.models import BlockType
from openlargeprint.ocr.base import DocumentOcrEngine, EngineCapabilities, EnginePageResult, OcrDetectedLine


class MockTableOcrEngine(DocumentOcrEngine):
    """Deterministic OCR engine emitting a 3x3 table and a bottom footnote."""

    @property
    def engine_name(self) -> str:
        return "mock_table_engine"

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_name=self.engine_name,
            supports_layout=True,
            supports_confidence=True,
            supported_languages=["en"],
        )

    def is_available(self) -> bool:
        return True

    def analyze_page(self, pil_image: Image.Image, page_num: int = 1, *, cancellation=None) -> EnginePageResult:
        scale = 200.0 / 72.0
        # Invert helper: PDF y_pt -> pixel Y
        def y_to_px(y_pt: float) -> float:
            return (792.0 - y_pt) * scale

        def x_to_px(x_pt: float) -> float:
            return x_pt * scale

        def make_line(text: str, x0_pt: float, y0_pt: float, x1_pt: float, y1_pt: float, conf: float = 0.98) -> OcrDetectedLine:
            px_x0 = x_to_px(x0_pt)
            px_x1 = x_to_px(x1_pt)
            px_y0 = y_to_px(y1_pt)
            px_y1 = y_to_px(y0_pt)
            poly = [(px_x0, px_y0), (px_x1, px_y0), (px_x1, px_y1), (px_x0, px_y1)]
            return OcrDetectedLine(text=text, polygon=poly, confidence=conf)

        lines = [
            # Title
            make_line("Scanned Legal Case Analysis", 72, 715, 350, 730, 0.99),
            # Table Row 0 (Header)
            make_line("Case Name", 72, 625, 200, 640, 0.98),
            make_line("Year", 240, 625, 300, 640, 0.98),
            make_line("Jurisdiction", 420, 625, 530, 640, 0.98),
            # Table Row 1
            make_line("Donoghue v Stevenson", 72, 585, 220, 600, 0.97),
            make_line("1932", 240, 585, 290, 600, 0.97),
            make_line("House of Lords", 420, 585, 540, 600, 0.97),
            # Table Row 2
            make_line("Hedley Byrne v Heller", 72, 545, 220, 560, 0.97),
            make_line("1964", 240, 545, 290, 560, 0.97),
            make_line("House of Lords", 420, 545, 540, 560, 0.97),
            # Footnote at bottom (y=80 <= 0.28 * 792)
            make_line("1 Hedley Byrne established liability for negligent misstatement.", 72, 68, 450, 80, 0.96),
        ]
        return EnginePageResult(lines=lines, elapse_seconds=0.05)


def test_scanned_table_extraction_with_image_crop(tmp_path: Path):
    """Verify that ScannedPageExtractor detects TableStructure, attaches image_asset crop, and extracts footnotes (TBL-001, FN-001)."""
    # Create empty PDF page
    pdf_path = tmp_path / "scanned_table.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(100, 700, "Dummy")
    c.showPage()
    c.save()

    doc = pdfium.PdfDocument(pdf_path)
    page = doc[0]

    extractor = ScannedPageExtractor(ocr_engine=MockTableOcrEngine(), dpi=200.0)
    blocks = extractor.extract_page(page, page_num=1, start_block_idx=0)

    # 1. Verify Table block and TableStructure
    tbl_blocks = [b for b in blocks if b.type == BlockType.TABLE]
    assert len(tbl_blocks) == 1
    tbl = tbl_blocks[0]
    assert tbl.table_structure is not None
    assert tbl.table_structure.row_count == 3
    assert tbl.table_structure.column_count == 3
    assert tbl.table_structure.rows[0][0].text == "Case Name"
    assert "Donoghue" in tbl.table_structure.rows[1][0].text

    # 2. Verify retained source-table image crop asset (TBL-001)
    assert tbl.image_asset is not None
    assert tbl.image_asset.file_path is not None
    assert Path(tbl.image_asset.file_path).exists()
    assert tbl.image_asset.width > 0
    assert tbl.image_asset.height > 0

    # 3. Verify Footnote block (FN-001)
    fn_blocks = [b for b in blocks if b.type == BlockType.FOOTNOTE]
    assert len(fn_blocks) == 1
    assert "Hedley Byrne" in fn_blocks[0].text
