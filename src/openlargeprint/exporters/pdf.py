"""Reflowed large-print PDF exporter using ReportLab Platypus (OUT-003, OUT-007..009)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A3, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image as PlatypusImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table as PlatypusTable,
    TableStyle,
)

from openlargeprint.ir.models import Block, BlockType, DocumentIR, TableStructure, TextDirection
from openlargeprint.layout.table import TableTier, evaluate_table_fit
from openlargeprint.security.isolation import log_safe_info
from openlargeprint.text.bidi import reorder_bidi_for_display
from .base import BaseExporter, ExportOptions, PaperSize
from .fonts import ensure_arabic_font as _ensure_arabic_font
from .fonts import resolve_reportlab_family

FRAME_PADDING_PT = 6.0
IMAGE_HEIGHT_FRACTION = 0.92

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
        usable_width = doc_template.width - 2 * FRAME_PADDING_PT
        usable_height = doc_template.height - 2 * FRAME_PADDING_PT

        for block in doc.blocks:
            flowables = self._block_to_flowables(block, options, styles, usable_width, usable_height)
            story.extend(flowables)

        # 4. Build PDF with NumberedCanvas
        doc_template.build(story, canvasmaker=NumberedCanvas)
        log_safe_info(f"Large-Print PDF generated successfully: {output_path.name}")
        return output_path

    def _get_or_create_monochrome_image(self, file_path: str) -> str:
        """Convert image to high-contrast grayscale for laser printing."""
        try:
            from PIL import Image, ImageEnhance
            src_p = Path(file_path)
            mono_path = src_p.parent / f"{src_p.stem}_mono.png"
            if mono_path.exists():
                return str(mono_path)
            with Image.open(src_p) as im:
                gray = im.convert("L")
                enhancer = ImageEnhance.Contrast(gray)
                enhanced = enhancer.enhance(1.15)
                enhanced.save(mono_path, format="PNG")
                return str(mono_path)
        except Exception:
            return file_path

    def _create_typography_styles(self, options: ExportOptions) -> dict[str, ParagraphStyle]:
        """Create paragraph styles calibrated to the chosen preset (OUT-006, FN-002)."""
        body_pt = options.body_pt
        leading_pt = body_pt * options.line_spacing
        arabic_font = _ensure_arabic_font()
        faces = resolve_reportlab_family(options.font_family, options.fallback_font)
        font_regular = faces["normal"]
        font_bold = faces["bold"]
        font_italic = faces["italic"]
        is_mono = options.monochrome

        c_title = HexColor("#000000") if is_mono else HexColor("#111111")
        c_h2 = HexColor("#000000") if is_mono else HexColor("#222222")
        c_body = HexColor("#000000") if is_mono else HexColor("#111111")
        c_fn = HexColor("#000000") if is_mono else HexColor("#444444")
        c_cap = HexColor("#000000") if is_mono else HexColor("#333333")
        c_warn = HexColor("#000000") if is_mono else HexColor("#994400")
        c_marker = HexColor("#000000") if is_mono else HexColor("#555555")

        return {
            "title": ParagraphStyle(
                "Title",
                fontName=font_bold,
                fontSize=max(28.0, body_pt * 1.5),
                leading=max(36.0, body_pt * 1.5 * 1.25),
                textColor=c_title,
                spaceBefore=16,
                spaceAfter=14,
                keepWithNext=True,
            ),
            "title_rtl": ParagraphStyle(
                "TitleRtl",
                fontName=arabic_font,
                fontSize=max(28.0, body_pt * 1.5),
                leading=max(36.0, body_pt * 1.5 * 1.25),
                textColor=c_title,
                alignment=TA_RIGHT,
                spaceBefore=16,
                spaceAfter=14,
                keepWithNext=True,
            ),
            "h1": ParagraphStyle(
                "H1",
                fontName=font_bold,
                fontSize=max(26.0, body_pt * 1.4),
                leading=max(34.0, body_pt * 1.4 * 1.25),
                textColor=c_title,
                spaceBefore=18,
                spaceAfter=10,
                keepWithNext=True,
            ),
            "h1_rtl": ParagraphStyle(
                "H1Rtl",
                fontName=arabic_font,
                fontSize=max(26.0, body_pt * 1.4),
                leading=max(34.0, body_pt * 1.4 * 1.25),
                textColor=c_title,
                alignment=TA_RIGHT,
                spaceBefore=18,
                spaceAfter=10,
                keepWithNext=True,
            ),
            "h2": ParagraphStyle(
                "H2",
                fontName=font_bold,
                fontSize=max(23.0, body_pt * 1.25),
                leading=max(30.0, body_pt * 1.25 * 1.25),
                textColor=c_h2,
                spaceBefore=14,
                spaceAfter=8,
                keepWithNext=True,
            ),
            "h2_rtl": ParagraphStyle(
                "H2Rtl",
                fontName=arabic_font,
                fontSize=max(23.0, body_pt * 1.25),
                leading=max(30.0, body_pt * 1.25 * 1.25),
                textColor=c_h2,
                alignment=TA_RIGHT,
                spaceBefore=14,
                spaceAfter=8,
                keepWithNext=True,
            ),
            "h3": ParagraphStyle(
                "H3",
                fontName=font_bold,
                fontSize=max(21.0, body_pt * 1.15),
                leading=max(28.0, body_pt * 1.15 * 1.25),
                textColor=c_h2,
                spaceBefore=12,
                spaceAfter=6,
                keepWithNext=True,
            ),
            "h3_rtl": ParagraphStyle(
                "H3Rtl",
                fontName=arabic_font,
                fontSize=max(21.0, body_pt * 1.15),
                leading=max(28.0, body_pt * 1.15 * 1.25),
                textColor=c_h2,
                alignment=TA_RIGHT,
                spaceBefore=12,
                spaceAfter=6,
                keepWithNext=True,
            ),
            "body": ParagraphStyle(
                "Body",
                fontName=font_regular,
                fontSize=body_pt,
                leading=leading_pt,
                textColor=c_body,
                spaceAfter=body_pt * 0.55,
            ),
            "body_rtl": ParagraphStyle(
                "BodyRtl",
                fontName=arabic_font,
                fontSize=body_pt,
                leading=leading_pt,
                textColor=c_body,
                alignment=TA_RIGHT,
                spaceAfter=body_pt * 0.55,
            ),
            "list": ParagraphStyle(
                "List",
                fontName=font_regular,
                fontSize=body_pt,
                leading=leading_pt,
                textColor=c_body,
                leftIndent=24,
                spaceAfter=body_pt * 0.35,
            ),
            "list_rtl": ParagraphStyle(
                "ListRtl",
                fontName=arabic_font,
                fontSize=body_pt,
                leading=leading_pt,
                textColor=c_body,
                alignment=TA_RIGHT,
                rightIndent=24,
                spaceAfter=body_pt * 0.35,
            ),
            "quote": ParagraphStyle(
                "Quote",
                fontName=font_italic,
                fontSize=body_pt,
                leading=leading_pt,
                textColor=c_h2,
                leftIndent=30,
                spaceBefore=8,
                spaceAfter=body_pt * 0.5,
            ),
            "quote_rtl": ParagraphStyle(
                "QuoteRtl",
                fontName=arabic_font,
                fontSize=body_pt,
                leading=leading_pt,
                textColor=c_h2,
                alignment=TA_RIGHT,
                rightIndent=30,
                spaceBefore=8,
                spaceAfter=body_pt * 0.5,
            ),
            "footnote": ParagraphStyle(
                "Footnote",
                fontName=font_italic,
                fontSize=max(14.0, body_pt * 0.8),
                leading=max(14.0, body_pt * 0.8) * 1.3,
                textColor=c_fn,
                spaceAfter=8,
            ),
            "footnote_rtl": ParagraphStyle(
                "FootnoteRtl",
                fontName=arabic_font,
                fontSize=max(14.0, body_pt * 0.8),
                leading=max(14.0, body_pt * 0.8) * 1.3,
                textColor=c_fn,
                alignment=TA_RIGHT,
                spaceAfter=8,
            ),
            "caption": ParagraphStyle(
                "Caption",
                fontName=font_bold,
                fontSize=max(14.0, body_pt * 0.85),
                leading=max(14.0, body_pt * 0.85) * 1.3,
                textColor=c_cap,
                alignment=TA_CENTER,
                spaceBefore=6,
                spaceAfter=10,
            ),
            "caption_rtl": ParagraphStyle(
                "CaptionRtl",
                fontName=arabic_font,
                fontSize=max(14.0, body_pt * 0.85),
                leading=max(14.0, body_pt * 0.85) * 1.3,
                textColor=c_cap,
                alignment=TA_RIGHT,
                spaceBefore=6,
                spaceAfter=10,
            ),
            "table_cell": ParagraphStyle(
                "TableCell",
                fontName=font_regular,
                fontSize=max(14.0, body_pt * 0.85),
                leading=max(14.0, body_pt * 0.85) * 1.25,
                textColor=c_body,
            ),
            "table_cell_rtl": ParagraphStyle(
                "TableCellRtl",
                fontName=arabic_font,
                fontSize=max(14.0, body_pt * 0.85),
                leading=max(14.0, body_pt * 0.85) * 1.25,
                textColor=c_body,
                alignment=TA_RIGHT,
            ),
            "table_header": ParagraphStyle(
                "TableHeader",
                fontName=font_bold,
                fontSize=max(14.0, body_pt * 0.85),
                leading=max(14.0, body_pt * 0.85) * 1.25,
                textColor=c_body,
            ),
            "table_header_rtl": ParagraphStyle(
                "TableHeaderRtl",
                fontName=arabic_font,
                fontSize=max(14.0, body_pt * 0.85),
                leading=max(14.0, body_pt * 0.85) * 1.25,
                textColor=c_body,
                alignment=TA_RIGHT,
            ),
            "table_warning": ParagraphStyle(
                "TableWarning",
                fontName=font_italic,
                fontSize=max(12.0, body_pt * 0.75),
                leading=max(12.0, body_pt * 0.75) * 1.25,
                textColor=c_warn,
                spaceBefore=6,
                spaceAfter=4,
            ),
            "page_marker": ParagraphStyle(
                "PageMarker",
                fontName=font_bold,
                fontSize=max(12.0, body_pt * 0.7),
                leading=max(12.0, body_pt * 0.7) * 1.3,
                textColor=c_marker,
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
        usable_height: float = 0.0,
    ) -> List[object]:
        """Convert a semantic Block into ReportLab Platypus flowable elements."""
        flowables: List[object] = []
        is_rtl = block.text_direction == TextDirection.RTL

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
            base_key = "title" if block.type == BlockType.TITLE else (f"h{level}" if level in (1, 2, 3) else "h3")
            style_key = f"{base_key}_rtl" if is_rtl else base_key
            raw_text = block.text or ""
            reordered = reorder_bidi_for_display(raw_text, TextDirection.RTL) if is_rtl else raw_text
            safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables.append(Paragraph(safe_text, styles[style_key]))
            return flowables

        # Handle lists
        if block.type == BlockType.LIST:
            raw_text = (block.text or "").lstrip("•-* \t")
            reordered = reorder_bidi_for_display(raw_text, TextDirection.RTL) if is_rtl else raw_text
            # Escape text first, then add the bullet with numeric entities so the
            # entity is not itself escaped (renders a real bullet, not "&nbsp;").
            safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if is_rtl:
                flowables.append(Paragraph(f"{safe_text}&nbsp;&nbsp;&#8226;", styles["list_rtl"]))
            else:
                flowables.append(Paragraph(f"&#8226;&nbsp;&nbsp;{safe_text}", styles["list"]))
            return flowables

        # Handle quotes
        if block.type == BlockType.QUOTE:
            raw_text = block.text or ""
            reordered = reorder_bidi_for_display(raw_text, TextDirection.RTL) if is_rtl else raw_text
            safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            style_key = "quote_rtl" if is_rtl else "quote"
            flowables.append(Paragraph(safe_text, styles[style_key]))
            return flowables

        # Handle captions
        if block.type == BlockType.CAPTION:
            raw_text = block.text or ""
            reordered = reorder_bidi_for_display(raw_text, TextDirection.RTL) if is_rtl else raw_text
            safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            style_key = "caption_rtl" if is_rtl else "caption"
            flowables.append(Paragraph(safe_text, styles[style_key]))
            return flowables

        # Handle footnotes (FN-001, FN-002: enforce minimum readable size >= 14pt)
        if block.type == BlockType.FOOTNOTE:
            raw_text = block.text or ""
            reordered = reorder_bidi_for_display(raw_text, TextDirection.RTL) if is_rtl else raw_text
            safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            style_key = "footnote_rtl" if is_rtl else "footnote"
            # Subtle divider above footnote
            flowables.append(
                HRFlowable(
                    width="35%",
                    thickness=0.75,
                    color=HexColor("#000000") if options.monochrome else HexColor("#888888"),
                    spaceBefore=8,
                    spaceAfter=4,
                    hAlign="RIGHT" if is_rtl else "LEFT",
                )
            )
            flowables.append(Paragraph(safe_text, styles[style_key]))
            return flowables

        # Handle tables (TBL-001, TBL-002, FN-002)
        if block.type == BlockType.TABLE and block.table_structure:
            return self._render_pdf_table(block, options, styles, usable_width, is_rtl, usable_height)

        # Handle images (IMG-001, IMG-003)
        if block.type == BlockType.IMAGE and block.image_asset:
            asset = block.image_asset
            if asset.file_path and Path(asset.file_path).exists():
                aspect = asset.width / max(1.0, asset.height)
                # Fit image within the usable width AND height without distortion (IMG-003)
                display_w = min(usable_width, float(asset.width * 72.0 / 96.0))
                display_h = display_w / aspect
                # Leave headroom for the frame's own padding so the flowable always fits.
                max_h = (usable_height * IMAGE_HEIGHT_FRACTION) if usable_height and usable_height > 0 else None
                if max_h is not None and display_h > max_h:
                    display_h = max_h
                    display_w = display_h * aspect

                img_path = asset.file_path
                if options.monochrome:
                    img_path = self._get_or_create_monochrome_image(asset.file_path)

                flowables.append(Spacer(1, 10))
                flowables.append(PlatypusImage(img_path, width=display_w, height=display_h))
                flowables.append(Spacer(1, 10))
            return flowables

        # Regular body paragraph
        raw_text = block.text or ""
        reordered = reorder_bidi_for_display(raw_text, TextDirection.RTL) if is_rtl else raw_text
        safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        style_key = "body_rtl" if is_rtl else "body"
        flowables.append(Paragraph(safe_text, styles[style_key]))
        return flowables

    def _render_pdf_table(
        self,
        block: Block,
        options: ExportOptions,
        styles: dict[str, ParagraphStyle],
        usable_width: float,
        is_rtl: bool,
        usable_height: float = 0.0,
    ) -> List[object]:
        """Render table with large-print scaling, fallback cascade, and RTL support (TBL-001, TBL-002, FN-002)."""
        table_struct = block.table_structure
        if not table_struct or not table_struct.rows:
            return []

        flowables: List[object] = []
        min_readable_size = max(14.0, options.body_pt * 0.8)
        fit = evaluate_table_fit(
            table_struct,
            available_width=usable_width,
            font_pt=options.body_pt,
            min_readable_pt=min_readable_size,
        )

        # Render visible warning if table required fallback/linearization (TBL-002)
        if fit.warning or block.warnings:
            all_warnings = list(block.warnings)
            if fit.warning and fit.warning not in all_warnings:
                all_warnings.append(fit.warning)
            for warn in all_warnings:
                reordered_warn = reorder_bidi_for_display(warn, TextDirection.RTL) if is_rtl else warn
                safe_warn = reordered_warn.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                flowables.append(Paragraph(f"⚠️ [Table Note] {safe_warn}", styles["table_warning"]))

        # Tier 3: Linearized accessible cards (TBL-001)
        if fit.tier == TableTier.LINEARIZE:
            if block.image_asset and block.image_asset.file_path and Path(block.image_asset.file_path).exists():
                asset = block.image_asset
                aspect = asset.width / max(1.0, asset.height)
                disp_w = min(usable_width, float(asset.width * 72.0 / 96.0))
                disp_h = disp_w / aspect
                if usable_height > 0 and disp_h > usable_height * IMAGE_HEIGHT_FRACTION:
                    disp_h = usable_height * IMAGE_HEIGHT_FRACTION
                    disp_w = disp_h * aspect
                retained_path = asset.file_path
                if options.monochrome:
                    retained_path = self._get_or_create_monochrome_image(asset.file_path)
                flowables.append(Spacer(1, 8))
                flowables.append(PlatypusImage(retained_path, width=disp_w, height=disp_h))
                flowables.append(Spacer(1, 8))

            lines = (fit.linearized_text or table_struct.to_linearized_text()).split("\n")
            for line in lines:
                if not line.strip():
                    continue
                reordered = reorder_bidi_for_display(line, TextDirection.RTL) if is_rtl else line
                safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                style_key = "footnote_rtl" if is_rtl else "footnote"
                flowables.append(Paragraph(safe_text, styles[style_key]))
            flowables.append(Spacer(1, 10))
            return flowables

        # Tier 2: Split columns sub-tables (TBL-001)
        if fit.tier == TableTier.SPLIT and fit.split_tables:
            for st in fit.split_tables:
                t_flow = self._build_platypus_table(st, options, styles, usable_width, is_rtl)
                if t_flow:
                    flowables.append(Spacer(1, 8))
                    flowables.append(t_flow)
                    flowables.append(Spacer(1, 8))
            return flowables

        # Tier 1: Enlarged semantic table
        t_flow = self._build_platypus_table(
            table_struct, options, styles, usable_width, is_rtl, fit.column_widths
        )
        if t_flow:
            flowables.append(Spacer(1, 8))
            flowables.append(t_flow)
            flowables.append(Spacer(1, 10))
        return flowables

    def _build_platypus_table(
        self,
        table_struct: TableStructure,
        options: ExportOptions,
        styles: dict[str, ParagraphStyle],
        usable_width: float,
        is_rtl: bool,
        col_widths: Optional[List[float]] = None,
    ) -> Optional[PlatypusTable]:
        """Construct styled Platypus Table with auto-wrapping, headers, and bidi support."""
        if not table_struct.rows:
            return None

        col_count = table_struct.column_count
        if col_count == 0:
            return None

        # Build table cells with wrapped Paragraphs
        data: List[List[object]] = []
        for r_idx, row in enumerate(table_struct.rows):
            row_cells: List[object] = []
            is_header_row = (r_idx == 0 and table_struct.has_header)

            for c_idx in range(col_count):
                cell_text = row[c_idx].text if c_idx < len(row) else ""
                reordered = reorder_bidi_for_display(cell_text, TextDirection.RTL) if is_rtl else cell_text
                safe_text = reordered.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

                if is_header_row:
                    style_key = "table_header_rtl" if is_rtl else "table_header"
                else:
                    style_key = "table_cell_rtl" if is_rtl else "table_cell"

                row_cells.append(Paragraph(safe_text, styles[style_key]))

            if is_rtl:
                row_cells.reverse()
            data.append(row_cells)

        # Allocate column widths
        calculated_widths: List[float] = []
        if col_widths and len(col_widths) == col_count:
            calculated_widths = list(col_widths)
        else:
            default_w = usable_width / max(1, col_count)
            calculated_widths = [default_w] * col_count

        if is_rtl:
            calculated_widths.reverse()

        grid_color = HexColor("#000000") if options.monochrome else HexColor("#D0D0D0")
        header_bg = HexColor("#E5E5E5") if options.monochrome else HexColor("#F2F2F2")

        t = PlatypusTable(data, colWidths=calculated_widths, repeatRows=1 if table_struct.has_header else 0, splitInRow=1)
        t_style = [
            ("GRID", (0, 0), (-1, -1), 1.0 if options.monochrome else 0.75, grid_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        if table_struct.has_header:
            t_style.append(("BACKGROUND", (0, 0), (-1, 0), header_bg))

        t.setStyle(TableStyle(t_style))
        return t
