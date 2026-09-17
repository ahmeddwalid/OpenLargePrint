"""Reflowed large-print PDF exporter using ReportLab Platypus (OUT-003, OUT-007..009)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image as PlatypusImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from openlargeprint.ir.models import Block, BlockType, DocumentIR
from openlargeprint.security.isolation import log_safe_info
from .base import BaseExporter, ExportOptions, PaperSize, PresetName


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and render total page count and print reminder (OUT-009)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(HexColor("#555555"))

        # Footer: page number and print scaling notice (OUT-009)
        footer_text = f"Page {self._pageNumber} of {total_pages}   |   Print at 100% / actual size (do not scale to fit)"
        self.drawRightString(self._pagesize[0] - 20 * mm, 12 * mm, footer_text)
        self.restoreState()


class PdfExporter(BaseExporter):
    """Renders DocumentIR into an accessible, single-column reflowed large-print PDF."""

    def export(self, doc: DocumentIR, output_path: Path, options: Optional[ExportOptions] = None) -> Path:
        """Render DocumentIR into target large-print PDF."""
        if options is None:
            options = ExportOptions()

        log_safe_info(
            f"Exporting DocumentIR to Large-Print PDF at {options.body_pt}pt ({options.paper_size.value}) -> {output_path.name}"
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Physical page dimensions & margins (OUT-007, OUT-008)
        if options.paper_size == PaperSize.A3:
            page_size = A3
            margin = 25 * mm
        else:
            page_size = A4
            margin = 20 * mm

        doc_template = SimpleDocTemplate(
            str(output_path),
            pagesize=page_size,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
            title=doc.metadata.title or "OpenLargePrint Document",
            author="OpenLargePrint",
        )

        # 2. Typography Styles (OUT-001, OUT-006, FN-002)
        styles = self._create_typography_styles(options)

        # 3. Build Story Flowables
        story: List[object] = []
        usable_width = doc_template.width

        for block in doc.blocks:
            flowables = self._block_to_flowables(block, options, styles, usable_width)
            story.extend(flowables)

        # 4. Build PDF with NumberedCanvas
        doc_template.build(story, canvasmaker=NumberedCanvas)
        log_safe_info(f"Large-Print PDF generated successfully: {output_path.name}")
        return output_path

    def _create_typography_styles(self, options: ExportOptions) -> dict[str, ParagraphStyle]:
        """Create paragraph styles calibrated to the chosen preset (OUT-006, FN-002)."""
        body_pt = options.body_pt
        leading_pt = body_pt * options.line_spacing

        return {
            "title": ParagraphStyle(
                "Title",
                fontName="Helvetica-Bold",
                fontSize=max(28.0, body_pt * 1.5),
                leading=max(36.0, body_pt * 1.5 * 1.25),
                textColor=HexColor("#111111"),
                spaceBefore=16,
                spaceAfter=14,
                keepWithNext=True,
            ),
            "h1": ParagraphStyle(
                "H1",
                fontName="Helvetica-Bold",
                fontSize=max(26.0, body_pt * 1.4),
                leading=max(34.0, body_pt * 1.4 * 1.25),
                textColor=HexColor("#111111"),
                spaceBefore=18,
                spaceAfter=10,
                keepWithNext=True,
            ),
            "h2": ParagraphStyle(
                "H2",
                fontName="Helvetica-Bold",
                fontSize=max(23.0, body_pt * 1.25),
                leading=max(30.0, body_pt * 1.25 * 1.25),
                textColor=HexColor("#222222"),
                spaceBefore=14,
                spaceAfter=8,
                keepWithNext=True,
            ),
            "h3": ParagraphStyle(
                "H3",
                fontName="Helvetica-Bold",
                fontSize=max(21.0, body_pt * 1.15),
                leading=max(28.0, body_pt * 1.15 * 1.25),
                textColor=HexColor("#222222"),
                spaceBefore=12,
                spaceAfter=6,
                keepWithNext=True,
            ),
            "body": ParagraphStyle(
                "Body",
                fontName="Helvetica",
                fontSize=body_pt,
                leading=leading_pt,
                textColor=HexColor("#111111"),
                spaceAfter=body_pt * 0.55,
            ),
            "list": ParagraphStyle(
                "List",
                fontName="Helvetica",
                fontSize=body_pt,
                leading=leading_pt,
                textColor=HexColor("#111111"),
                leftIndent=24,
                spaceAfter=body_pt * 0.35,
            ),
            "quote": ParagraphStyle(
                "Quote",
                fontName="Helvetica-Oblique",
                fontSize=body_pt,
                leading=leading_pt,
                textColor=HexColor("#222222"),
                leftIndent=30,
                spaceBefore=8,
                spaceAfter=body_pt * 0.5,
            ),
            "footnote": ParagraphStyle(
                "Footnote",
                fontName="Helvetica-Oblique",
                fontSize=max(14.0, body_pt * 0.8),
                leading=max(14.0, body_pt * 0.8) * 1.3,
                textColor=HexColor("#444444"),
                spaceAfter=8,
            ),
            "page_marker": ParagraphStyle(
                "PageMarker",
                fontName="Helvetica-Bold",
                fontSize=max(12.0, body_pt * 0.7),
                leading=max(12.0, body_pt * 0.7) * 1.3,
                textColor=HexColor("#555555"),
                alignment=1,  # Center
                spaceBefore=body_pt * 0.8,
                spaceAfter=body_pt * 0.5,
                keepWithNext=True,
            ),
        }

    def _block_to_flowables(
        self,
        block: Block,
        options: ExportOptions,
        styles: dict[str, ParagraphStyle],
        usable_width: float,
    ) -> List[object]:
        """Convert a semantic Block into ReportLab Platypus flowable elements."""
        flowables: List[object] = []

        # Handle page markers (OUT-005)
        if block.type == BlockType.PAGE_MARKER:
            if options.include_page_markers and block.page_marker is not None:
                flowables.append(
                    Paragraph(f"— Original Page {block.page_marker} —", styles["page_marker"])
                )
            return flowables

        # Handle headings
        if block.type in (BlockType.TITLE, BlockType.HEADING):
            level = block.level or 1
            style_key = "title" if block.type == BlockType.TITLE else (f"h{level}" if level in (1, 2, 3) else "h3")
            safe_text = (block.text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(safe_text, styles[style_key]))
            return flowables

        # Handle lists
        if block.type == BlockType.LIST:
            raw_text = (block.text or "").lstrip("•-* \t")
            safe_text = f"• &nbsp; {raw_text}".replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(safe_text, styles["list"]))
            return flowables

        # Handle quotes
        if block.type == BlockType.QUOTE:
            safe_text = (block.text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(safe_text, styles["quote"]))
            return flowables

        # Handle footnotes and captions (FN-002)
        if block.type in (BlockType.FOOTNOTE, BlockType.CAPTION):
            safe_text = (block.text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(safe_text, styles["footnote"]))
            return flowables

        # Handle images (IMG-001, IMG-003)
        if block.type == BlockType.IMAGE and block.image_asset:
            asset = block.image_asset
            if asset.file_path and Path(asset.file_path).exists():
                aspect = asset.width / max(1.0, asset.height)
                # Fit image to width without distortion (IMG-003)
                display_w = min(usable_width, float(asset.width * 72.0 / 96.0))
                display_h = display_w / aspect
                flowables.append(Spacer(1, 10))
                flowables.append(PlatypusImage(asset.file_path, width=display_w, height=display_h))
                flowables.append(Spacer(1, 10))
            return flowables

        # Regular body paragraph
        safe_text = (block.text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        flowables.append(Paragraph(safe_text, styles["body"]))
        return flowables
