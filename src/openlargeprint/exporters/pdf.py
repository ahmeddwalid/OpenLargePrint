"""Large-print PDF built from DocumentIR with ReportLab (OUT-003, OUT-005..009).

Text is set ragged-right in Atkinson Hyperlegible at the chosen size, with
headings, hanging-indent lists, answer lines, boxed notes, real tables and
pictures enlarged with the text. A thin rule and a label mark where each
original page begins, and the footer says which original pages a sheet holds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A3, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    HRFlowable,
    Image as PlatypusImage,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table as PlatypusTable,
    TableStyle,
)

from openlargeprint.ir.models import Block, BlockType, DocumentIR, PageMetadata, TableStructure, TextDirection
from openlargeprint.layout.table import TableTier, evaluate_table_fit, iter_visible_cells
from openlargeprint.security.isolation import log_safe_info
from openlargeprint.text.bidi import reorder_bidi_for_display
from .base import BaseExporter, ExportOptions, PaperSize
from .common import (
    BLANK_TOKEN,
    PRINT_REMINDER,
    caption_label,
    has_original_crop,
    is_retained_page,
    page_label,
    pages_by_number,
    picture_size,
    reader_note,
    split_marker,
    styled_segments,
    table_as_entries,
)
from .fonts import FontSet, markup, output_fonts

# Kept for callers that size images against the frame.
FRAME_PADDING_PT = 0.0
IMAGE_HEIGHT_FRACTION = 0.86

INK = HexColor("#1A1A1A")
MUTED = HexColor("#4A4A4A")
RULE = HexColor("#8A8A8A")
SHADE = HexColor("#EDEDED")


class _NumberedCanvas(canvas.Canvas):
    """Two passes: page count is known only after layout (OUT-009)."""

    def __init__(self, *args, footer_size: float = 12.0, font: str = "Helvetica", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved: List[dict] = []
        self.olp_sources: set = set()
        self.olp_current: Optional[int] = None
        self._footer_size = footer_size
        self._footer_font = font

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()
        self.olp_sources = {self.olp_current} if self.olp_current else set()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._footer(total)
            super().showPage()
        super().save()

    def _footer(self, total: int) -> None:
        width, _ = self._pagesize
        pages = sorted(p for p in self.olp_sources if p)
        if not pages:
            source = ""
        elif len(pages) == 1:
            source = f"Original page {pages[0]}"
        else:
            source = f"Original pages {pages[0]}–{pages[-1]}"
        self.saveState()
        self.setFillColor(MUTED)
        self.setFont(self._footer_font, self._footer_size)
        margin = 18 * mm
        if source:
            self.drawString(margin, 10 * mm, source)
        self.drawRightString(width - margin, 10 * mm, f"Page {self._pageNumber} of {total}")
        self.restoreState()


class _Doc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        page = getattr(flowable, "olp_page", None)
        if page:
            self.canv.olp_current = page
            self.canv.olp_sources.add(page)


class PdfExporter(BaseExporter):
    """Renders DocumentIR into a single-column large-print PDF."""

    def export(self, doc: DocumentIR, output_path: Path, options: Optional[ExportOptions] = None) -> Path:
        options = options or ExportOptions()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        log_safe_info(f"Writing large-print PDF at {options.body_pt}pt on {options.paper_size.value}")

        if options.paper_size == PaperSize.A3:
            page_size, margin = A3, 22 * mm
        else:
            page_size, margin = A4, 18 * mm
        bottom = margin + 8 * mm  # room for the footer
        fonts = output_fonts()
        template = _Doc(
            str(output_path), pagesize=page_size, leftMargin=margin, rightMargin=margin,
            topMargin=margin, bottomMargin=bottom,
            title=doc.metadata.title or "Large print", author="OpenLargePrint",
            subject=f"Large print, {options.body_pt:g} pt. Print at 100% (actual size).",
            creator="OpenLargePrint",
        )
        frame = Frame(margin, bottom, page_size[0] - 2 * margin, page_size[1] - margin - bottom,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body")
        template.addPageTemplates([PageTemplate(id="page", frames=[frame])])
        self._prepare(options, frame._width, frame._height, pages_by_number(doc))

        story: List[object] = []
        if doc.metadata.title:
            story.append(Paragraph(markup(doc.metadata.title, fonts), self._styles["doc_title"]))
        story.append(Paragraph(markup(PRINT_REMINDER, fonts), self._styles["note"]))
        story.append(Spacer(1, options.body_pt * 0.4))
        blocks = doc.blocks
        for index, block in enumerate(blocks):
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            flowables = self._block(block, following)
            for item in flowables:
                item.olp_page = block.source_page
            story.extend(flowables)
        if not blocks:
            story.append(Paragraph("This document has no readable content.", self._styles["body"]))

        footer = max(12.0, options.body_pt * 0.6)
        template.build(story, canvasmaker=lambda *a, **k: _NumberedCanvas(*a, footer_size=footer,
                                                                           font=fonts.regular, **k))
        return output_path

    def _prepare(self, options: ExportOptions, width: float, height: float,
                 pages: Optional[Dict[int, PageMetadata]] = None) -> None:
        """Fonts, styles and frame size used while building flowables."""
        self._fonts = output_fonts()
        self._styles = self._make_styles(options, self._fonts)
        self._options = options
        self._width = width
        self._height = height
        self._pages = pages or {}

    # ------------------------------------------------------------------
    def _make_styles(self, options: ExportOptions, fonts: FontSet) -> Dict[str, ParagraphStyle]:
        b = options.body_pt
        lead = b * options.line_spacing
        small = max(14.0, b * 0.82)
        base = dict(fontName=fonts.regular, textColor=INK, allowWidows=0, allowOrphans=0)

        def style(name, **kw):
            merged = dict(base)
            merged.update(kw)
            return ParagraphStyle(name, **merged)

        styles = {
            "doc_title": style("DocTitle", fontName=fonts.bold, fontSize=b * 1.7, leading=b * 2.05,
                               spaceAfter=b * 0.3),
            "h1": style("H1", fontName=fonts.bold, fontSize=b * 1.55, leading=b * 1.9,
                        spaceBefore=b * 1.0, spaceAfter=b * 0.45, keepWithNext=1),
            "h2": style("H2", fontName=fonts.bold, fontSize=b * 1.3, leading=b * 1.62,
                        spaceBefore=b * 0.9, spaceAfter=b * 0.4, keepWithNext=1),
            "h3": style("H3", fontName=fonts.bold, fontSize=b * 1.1, leading=b * 1.42,
                        spaceBefore=b * 0.75, spaceAfter=b * 0.35, keepWithNext=1),
            "body": style("Body", fontSize=b, leading=lead, spaceAfter=b * 0.6),
            "list": style("List", fontSize=b, leading=lead, spaceAfter=b * 0.35),
            "caption": style("Caption", fontName=fonts.italic, fontSize=max(small, b * 0.9),
                             leading=max(small, b * 0.9) * 1.35, spaceBefore=b * 0.2, spaceAfter=b * 0.7,
                             textColor=MUTED),
            "footnote": style("Footnote", fontSize=small, leading=small * 1.4, spaceAfter=b * 0.35),
            "note": style("Note", fontName=fonts.italic, fontSize=small, leading=small * 1.35,
                          textColor=MUTED, spaceAfter=b * 0.5),
            "aside": style("Aside", fontSize=b, leading=lead),
            "marker": style("Marker", fontName=fonts.bold, fontSize=max(12.0, b * 0.65),
                            leading=max(12.0, b * 0.65) * 1.3, textColor=MUTED, spaceAfter=b * 0.5,
                            keepWithNext=1),
            "cell": style("Cell", fontSize=max(small, b * 0.88), leading=max(small, b * 0.88) * 1.3),
            "cell_head": style("CellHead", fontName=fonts.bold, fontSize=max(small, b * 0.88),
                               leading=max(small, b * 0.88) * 1.3),
        }
        for key in list(styles):
            rtl = ParagraphStyle(f"{styles[key].name}Rtl", parent=styles[key], alignment=TA_RIGHT,
                                 fontName=fonts.arabic)
            styles[f"{key}_rtl"] = rtl
        return styles

    def _text(self, text: str, rtl: bool, block: Optional[Block] = None, offset: int = 0) -> str:
        if rtl:
            text = reorder_bidi_for_display(text, TextDirection.RTL)
            result = markup(text, self._fonts)
        else:
            result = "".join(
                f"{''.join(f'<{t}>' for t in tags)}{markup(segment, self._fonts)}{''.join(f'</{t}>' for t in reversed(tags))}"
                for segment, tags in styled_segments(text, block.styles if block else [], offset))
        return result.replace(BLANK_TOKEN, "<u>" + "&nbsp;" * 12 + "</u>").replace("\n", "<br/>")

    def _style(self, key: str, rtl: bool) -> ParagraphStyle:
        return self._styles[f"{key}_rtl" if rtl else key]

    def _block(self, block: Block, following: Optional[Block]) -> List[object]:
        options = self._options
        rtl = block.text_direction == TextDirection.RTL
        b = options.body_pt
        out: List[object] = []

        if block.type == BlockType.PAGE_MARKER:
            if not options.include_page_markers or block.page_marker is None:
                return out
            if options.page_break_on_source_page and block.page_marker > 1:
                out.append(PageBreak())
            else:
                out.append(CondPageBreak(b * 6))
            out.append(HRFlowable(width="100%", thickness=0.8, color=RULE, spaceBefore=b * 0.8, spaceAfter=b * 0.25))
            label = page_label(block.page_marker, self._pages.get(block.page_marker))
            out.append(Paragraph(markup(label, self._fonts), self._styles["marker"]))
            return out

        if block.type in (BlockType.TITLE, BlockType.HEADING):
            level = 1 if block.type == BlockType.TITLE else max(1, min(3, block.level or 2))
            style = self._style(f"h{level}", rtl)
            if following is not None and following.type in (BlockType.TABLE, BlockType.IMAGE):
                # Chaining a heading to a whole table or picture can push both to the
                # next sheet and leave a near-empty page; reserve room instead.
                out.append(CondPageBreak(style.leading * 2 + b * 8))
                style = ParagraphStyle(f"{style.name}Free", parent=style, keepWithNext=0)
            out.append(Paragraph(self._text(block.text or "", rtl), style))
            return out

        if block.type == BlockType.LIST:
            marker, rest = split_marker(block)
            style = self._style("list", rtl)
            indent = block.indent_level * b * 1.7
            if marker:
                marker_font = self._fonts.bold if block.role == "dialogue" else self._fonts.regular
                hang = max(b * 1.7, stringWidth(marker, marker_font, b) + b * 0.6)
                style = ParagraphStyle(f"List{block.id}", parent=style, leftIndent=indent + hang,
                                       bulletIndent=indent, bulletFontName=marker_font, bulletFontSize=b)
                para = Paragraph(self._text(rest, rtl, block, len(block.text or "") - len(rest)), style,
                                 bulletText=marker)
            else:
                para = Paragraph(self._text(block.text or "", rtl, block), style)
            out.append(para)
            self._note(block, out)
            return out

        if block.type == BlockType.CAPTION:
            label = caption_label(block)
            text = self._text(block.text or "", rtl, block)
            if label:
                text = f'<font name="{self._fonts.bold_italic}">{markup(label, self._fonts)}</font>{text}'
            out.append(Paragraph(text, self._style("caption", rtl)))
            return out

        if block.type == BlockType.FOOTNOTE:
            out.append(HRFlowable(width="30%", thickness=0.6, color=RULE, hAlign="RIGHT" if rtl else "LEFT",
                                  spaceBefore=b * 0.4, spaceAfter=b * 0.2))
            out.append(Paragraph(self._text(block.text or "", rtl, block), self._style("footnote", rtl)))
            return out

        if block.type == BlockType.ASIDE:
            if block.role == "page_note":
                out.append(Paragraph(self._text(block.text or "", rtl), self._style("note", rtl)))
                return out
            box = PlatypusTable([[Paragraph(self._text(block.text or "", rtl, block), self._style("aside", rtl))]],
                                colWidths=[self._width])
            box.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 1.0, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), b * 0.6), ("RIGHTPADDING", (0, 0), (-1, -1), b * 0.6),
                ("TOPPADDING", (0, 0), (-1, -1), b * 0.4), ("BOTTOMPADDING", (0, 0), (-1, -1), b * 0.5),
            ]))
            out.extend([box, Spacer(1, b * 0.6)])
            return out

        if block.type == BlockType.TABLE and block.table_structure:
            return self._table(block, rtl)

        if block.type == BlockType.IMAGE and block.image_asset:
            asset = block.image_asset
            if not asset.file_path or not Path(asset.file_path).exists():
                return out
            retained = is_retained_page(block)
            if retained:
                self._note(block, out)
            width, height = picture_size(block, self._width, self._height, b, retained=retained)
            image = PlatypusImage(self._picture_path(asset.file_path), width=width, height=height)
            image.hAlign = "CENTER"
            if following is not None and following.type == BlockType.CAPTION:
                image.keepWithNext = 1
            out.extend([Spacer(1, b * 0.3), image, Spacer(1, b * 0.4)])
            return out

        out.append(Paragraph(self._text(block.text or "", rtl, block), self._style("body", rtl)))
        self._note(block, out)
        return out

    def _note(self, block: Block, out: List[object]) -> None:
        note = reader_note(block)
        if note:
            out.append(Paragraph(markup(note, self._fonts), self._styles["note"]))
        asset = block.image_asset
        if has_original_crop(block) and asset.file_path and Path(asset.file_path).exists():
            width, height = picture_size(block, self._width, self._height, self._options.body_pt)
            image = PlatypusImage(self._picture_path(asset.file_path), width=width, height=height)
            image.hAlign = "LEFT"
            out.extend([image, Spacer(1, self._options.body_pt * 0.5)])

    def _picture_path(self, path: str) -> str:
        if not self._options.monochrome:
            return path
        try:
            from PIL import Image, ImageOps
            source = Path(path)
            target = source.with_name(f"{source.stem}_mono.png")
            if not target.exists():
                with Image.open(source) as image:
                    ImageOps.autocontrast(image.convert("L"), cutoff=1).save(target)
            return str(target)
        except Exception:
            return path

    # ------------------------------------------------------------------
    def _table(self, block: Block, rtl: bool) -> List[object]:
        table = block.table_structure
        options = self._options
        b = options.body_pt
        out: List[object] = []
        if not table or not table.rows:
            return out
        cell_pt = max(14.0, b * 0.88)
        fit = evaluate_table_fit(table, available_width=self._width, font_pt=cell_pt, min_readable_pt=14.0)
        notes = [w for w in [reader_note(block), fit.warning] if w]
        for note in dict.fromkeys(notes):
            out.append(Paragraph(markup(note, self._fonts), self._styles["note"]))
        if block.image_asset and block.image_asset.file_path and Path(block.image_asset.file_path).exists():
            width, height = picture_size(block, self._width, self._height, b)
            out.append(PlatypusImage(self._picture_path(block.image_asset.file_path), width=width, height=height))
            out.append(Spacer(1, b * 0.4))
        caption_style = ParagraphStyle("TableCaption", parent=self._style("caption", rtl), keepWithNext=1)
        if fit.tier == TableTier.LINEARIZE:
            if table.caption:
                out.append(Paragraph(self._text(table.caption, rtl), caption_style))
            lead_style = ParagraphStyle("TableLead", parent=self._style("body", rtl), fontName=self._fonts.bold,
                                        spaceAfter=b * 0.15, keepWithNext=1)
            detail_style = ParagraphStyle("TableDetail", parent=self._style("list", rtl), leftIndent=b * 1.4)
            for lead, details in table_as_entries(table):
                if lead:
                    out.append(Paragraph(self._text(lead, rtl), lead_style))
                for label, value in details:
                    text = self._text(value, rtl)
                    if label:
                        text = f"<b>{markup(label, self._fonts)}:</b> {text}"
                    out.append(Paragraph(text, detail_style))
                out.append(Spacer(1, b * 0.4))
            return out
        parts = fit.split_tables if fit.tier == TableTier.SPLIT and fit.split_tables else [table]
        for part in parts:
            widths = fit.column_widths if part is table and fit.column_widths and len(fit.column_widths) == part.column_count else None
            flow = self._grid(part, rtl, widths)
            if part.caption:
                out.append(Paragraph(self._text(part.caption, rtl), caption_style))
            if flow is not None:
                out.extend([flow, Spacer(1, b * 0.7)])
        return out

    def _grid(self, table: TableStructure, rtl: bool, widths: Optional[List[float]]) -> Optional[PlatypusTable]:
        columns = table.column_count
        if not columns:
            return None
        data: List[List[object]] = []
        for r, row in enumerate(table.rows):
            header = r == 0 and table.has_header
            cells = [Paragraph(self._text(row[c].text if c < len(row) else "", rtl),
                               self._style("cell_head" if header else "cell", rtl)) for c in range(columns)]
            if rtl:
                cells.reverse()
            data.append(cells)
        if rtl:
            # Reversing a row moves a merged cell's text to the far end of its span;
            # ReportLab draws the span's first cell, so move the text back there.
            for r, c, _cell, _rs, cs in iter_visible_cells(table):
                if cs > 1:
                    anchor, start = columns - c - 1, columns - c - cs
                    data[r][start], data[r][anchor] = data[r][anchor], data[r][start]
        if widths:
            scale = self._width / max(1.0, sum(widths))
            col_widths = [w * min(1.0, scale) for w in widths]
            if sum(col_widths) < self._width * 0.98:
                extra = (self._width - sum(col_widths)) / columns
                col_widths = [w + extra for w in col_widths]
        else:
            col_widths = [self._width / columns] * columns
        if rtl:
            col_widths.reverse()
        grid = PlatypusTable(data, colWidths=col_widths, repeatRows=1 if table.has_header else 0, splitInRow=1)
        pad = self._options.body_pt * 0.35
        style = [
            ("GRID", (0, 0), (-1, -1), 0.75, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), pad), ("RIGHTPADDING", (0, 0), (-1, -1), pad),
            ("TOPPADDING", (0, 0), (-1, -1), pad * 0.8), ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
        ]
        if table.has_header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), SHADE))
        for r, c, _cell, rs, cs in iter_visible_cells(table):
            if rs > 1 or cs > 1:
                start = columns - c - cs if rtl else c
                end = columns - c - 1 if rtl else c + cs - 1
                style.append(("SPAN", (start, r), (end, r + rs - 1)))
        grid.setStyle(TableStyle(style))
        return grid
