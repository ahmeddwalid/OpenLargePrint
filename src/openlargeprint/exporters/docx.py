"""Large-print Word document built from DocumentIR (OUT-001, OUT-005..009).

Headings use Word's own Heading styles, so the Navigation Pane and a table of
contents work. Numbered and lettered items get hanging indents, answer lines
stay visible, and the reading font is embedded in the file so the document
looks the same on a computer that does not have it installed.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Mm, Pt, RGBColor

from openlargeprint.ir.models import Block, BlockType, DocumentIR, TableStructure, TextDirection
from openlargeprint.layout.table import TableTier, evaluate_table_fit, iter_visible_cells
from openlargeprint.security.isolation import log_safe_info
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
from .fonts import FONT_FAMILY, bundled_font_dir

_ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]")
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x4A, 0x4A, 0x4A)
BLACK = RGBColor(0, 0, 0)
FONT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
FONT_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.obfuscatedFont"


# Child order Word requires inside paragraph and table properties (ECMA-376 Part 1, 17.3.1.26 and 17.4.60).
_PPR_ORDER = ("pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
              "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
              "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
              "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc",
              "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
              "sectPr", "pPrChange")
_RPR_ORDER = ("rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline",
              "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
              "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText",
              "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath")
_TBLPR_ORDER = ("tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize",
                "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook",
                "tblCaption", "tblDescription", "tblPrChange")


def _place(parent, element, order) -> None:
    """Insert ``element`` into ``parent`` at the position the schema requires, replacing a twin."""
    name = element.tag.split("}")[-1]
    existing = parent.find(qn(f"w:{name}"))
    if existing is not None:
        parent.remove(existing)
    later = order[order.index(name) + 1:]
    for child in parent:
        if child.tag.split("}")[-1] in later:
            child.addprevious(element)
            return
    parent.append(element)


def _set_size(run, points: float) -> None:
    """Run size for both Latin and complex-script (Arabic) text."""
    run.font.size = Pt(points)
    element = OxmlElement("w:szCs")
    element.set(qn("w:val"), str(int(round(points * 2))))
    _place(run._r.get_or_add_rPr(), element, _RPR_ORDER)


def clean_xml_string(text: Optional[str]) -> str:
    """Strip characters that XML 1.0 does not allow (OUT-001)."""
    return _ILLEGAL_XML_CHARS_RE.sub("", text) if text else ""


def _obfuscate(font: bytes, key: str) -> bytes:
    """Word's embedded-font obfuscation: the first 32 bytes XOR the reversed GUID."""
    guid = bytes.fromhex(key.strip("{}").replace("-", ""))[::-1]
    head = bytes(font[i] ^ guid[i % 16] for i in range(32))
    return head + font[32:]


class DocxExporter(BaseExporter):
    """Renders DocumentIR into a single-column large-print .docx file."""

    def export(self, doc: DocumentIR, output_path: Path, options: Optional[ExportOptions] = None) -> Path:
        options = options or ExportOptions()
        output_path = Path(output_path)
        log_safe_info(f"Writing large-print Word document at {options.body_pt}pt on {options.paper_size.value}")
        self._options = options
        self._pages = pages_by_number(doc)
        document = docx.Document()
        self._document = document
        section = document.sections[0]
        self._page_setup(section)
        self._styles(document)
        self._footer(section)

        settings = document.settings.element
        view = settings.find(qn("w:view"))
        if view is None:
            view = OxmlElement("w:view")
            settings.insert(0, view)
        view.set(qn("w:val"), "print")
        self._embed_fonts(document)
        props = document.core_properties
        props.title = clean_xml_string(doc.metadata.title) or "Large print"
        props.author = "OpenLargePrint"
        props.comments = f"Large print, {options.body_pt:g} pt on {options.paper_size.value}. Print at 100% (actual size)."

        self._width = Emu(section.page_width - section.left_margin - section.right_margin)
        self._height = Emu(section.page_height - section.top_margin - section.bottom_margin)
        if doc.metadata.title:
            document.add_paragraph(clean_xml_string(doc.metadata.title), style="Title")
        self._note_paragraph(PRINT_REMINDER)
        for block in doc.blocks:
            self._block(block)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output_path))
        return output_path

    # -- document setup ---------------------------------------------------
    def _page_setup(self, section) -> None:
        if self._options.paper_size == PaperSize.A3:
            section.page_width, section.page_height = Mm(297), Mm(420)
            margin = Mm(22)
        else:
            section.page_width, section.page_height = Mm(210), Mm(297)
            margin = Mm(18)
        section.left_margin = section.right_margin = section.top_margin = margin
        section.bottom_margin = margin + Mm(6)

    def _styles(self, document) -> None:
        b = self._options.body_pt
        styles = document.styles

        def base(style, size, bold=False, italic=False, color=INK, before=0.0, after=0.0, keep=False, spacing=None):
            font = style.font
            font.name = FONT_FAMILY
            font.size = Pt(size)
            font.bold = bold
            font.italic = italic
            font.color.rgb = BLACK if self._options.monochrome else color
            rpr = style.element.get_or_add_rPr()
            fonts = rpr.find(qn("w:rFonts"))
            if fonts is None:
                fonts = OxmlElement("w:rFonts")
                rpr.insert(0, fonts)
            for attr in ("w:ascii", "w:hAnsi", "w:eastAsia"):
                fonts.set(qn(attr), FONT_FAMILY)
            # Theme font references win over named fonts; the built-in headings carry them.
            for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                fonts.attrib.pop(qn(attr), None)
            # Arabic and other right-to-left runs use the complex-script size and weight.
            for tag, value in (("szCs", str(int(round(size * 2)))), ("bCs", None if bold else "0"),
                               ("iCs", None if italic else "0")):
                element = OxmlElement(f"w:{tag}")
                if value is not None:
                    element.set(qn("w:val"), value)
                _place(rpr, element, _RPR_ORDER)
            fonts.set(qn("w:cs"), "Noto Sans Arabic")
            fmt = style.paragraph_format
            fmt.space_before = Pt(before)
            fmt.space_after = Pt(after)
            fmt.keep_with_next = keep
            fmt.widow_control = True
            if spacing:
                fmt.line_spacing = spacing

        base(styles["Normal"], b, after=b * 0.6, spacing=self._options.line_spacing)
        base(styles["Title"], b * 1.7, bold=True, after=b * 0.3, spacing=1.1)
        title = styles["Title"].element.pPr
        if title is not None:
            border = title.find(qn("w:pBdr"))
            if border is not None:
                title.remove(border)
        base(styles["Heading 1"], b * 1.55, bold=True, before=b * 1.0, after=b * 0.45, keep=True, spacing=1.2)
        base(styles["Heading 2"], b * 1.3, bold=True, before=b * 0.9, after=b * 0.4, keep=True, spacing=1.2)
        base(styles["Heading 3"], b * 1.1, bold=True, before=b * 0.75, after=b * 0.35, keep=True, spacing=1.25)
        small = max(14.0, b * 0.82)
        for name, kwargs in (
            ("Caption", dict(size=max(small, b * 0.9), italic=True, color=MUTED, after=b * 0.7)),
            ("Original Page", dict(size=max(12.0, b * 0.65), bold=True, color=MUTED, before=b * 0.8, after=b * 0.5, keep=True)),
            ("Reader Note", dict(size=small, italic=True, color=MUTED, after=b * 0.5)),
            ("Footnote Text", dict(size=small, after=b * 0.35)),
            ("Boxed Note", dict(size=b, after=b * 0.6)),
            ("Quote", dict(size=b, italic=True, after=b * 0.6)),
            ("List Item", dict(size=b, after=b * 0.35)),
        ):
            try:
                style = styles[name]
            except KeyError:
                style = styles.add_style(name, 1)
                style.base_style = styles["Normal"]
            size = kwargs.pop("size")
            base(style, size, spacing=self._options.line_spacing if name in ("List Item", "Boxed Note", "Quote") else 1.3, **kwargs)
        quote = styles["Quote"].paragraph_format
        quote.left_indent = Pt(b * 1.4)
        quote.right_indent = Pt(0)
        marker = styles["Original Page"].element.get_or_add_pPr()
        _place(marker, self._border("top", "8", "8A8A8A"), _PPR_ORDER)
        box = styles["Boxed Note"].element.get_or_add_pPr()
        borders = OxmlElement("w:pBdr")
        for edge in ("top", "left", "bottom", "right"):
            borders.append(self._border(edge, "8", "8A8A8A", wrap=False))
        _place(box, borders, _PPR_ORDER)

    @staticmethod
    def _border(edge: str, size: str, color: str, wrap: bool = True):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "4")
        element.set(qn("w:color"), color)
        if not wrap:
            return element
        holder = OxmlElement("w:pBdr")
        holder.append(element)
        return holder

    def _footer(self, section) -> None:
        paragraph = section.footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        size = Pt(max(12.0, self._options.body_pt * 0.6))

        def text(value: str) -> None:
            run = paragraph.add_run(value)
            run.font.size = size
            run.font.color.rgb = MUTED

        def field(code: str) -> None:
            # begin / instruction / separate / shown value / end, each in its own
            # run so the value keeps the footer's size in every word processor.
            for kind in ("begin", "instr", "separate", "value", "end"):
                run = paragraph.add_run("1" if kind == "value" else None)
                run.font.size = size
                run.font.color.rgb = MUTED
                if kind == "instr":
                    element = OxmlElement("w:instrText")
                    element.set(qn("xml:space"), "preserve")
                    element.text = f" {code} "
                    run._r.append(element)
                elif kind != "value":
                    element = OxmlElement("w:fldChar")
                    element.set(qn("w:fldCharType"), kind)
                    run._r.append(element)

        text("Page ")
        field("PAGE")
        text(" of ")
        field("NUMPAGES")

    def _embed_fonts(self, document) -> None:
        """Embed the reading font so Word shows it on any computer."""
        try:
            font_part = document.part.part_related_by(RT.FONT_TABLE)
        except KeyError:
            return
        table = font_part.element if hasattr(font_part, "element") else None
        if table is None:
            from docx.oxml.parser import parse_xml
            table = parse_xml(font_part.blob)
        entry = OxmlElement("w:font")
        entry.set(qn("w:name"), FONT_FAMILY)
        for tag, filename in (("embedRegular", "Regular"), ("embedBold", "Bold"),
                              ("embedItalic", "Italic"), ("embedBoldItalic", "BoldItalic")):
            source = bundled_font_dir() / f"AtkinsonHyperlegible-{filename}.ttf"
            if not source.is_file():
                return
            key = "{" + str(uuid.uuid4()).upper() + "}"
            part = Part(PackURI(f"/word/fonts/font{filename}.odttf"), FONT_CONTENT_TYPE,
                        _obfuscate(source.read_bytes(), key), document.part.package)
            rid = font_part.relate_to(part, FONT_REL)
            embed = OxmlElement(f"w:{tag}")
            embed.set(qn("r:id"), rid)
            embed.set(qn("w:fontKey"), key)
            entry.append(embed)
        table.append(entry)
        if not hasattr(font_part, "element"):
            from lxml import etree
            font_part._blob = etree.tostring(table, xml_declaration=True, encoding="UTF-8", standalone=True)
        # w:settings children have a fixed order; Word reports a damaged file otherwise.
        settings = document.settings.element
        flag = OxmlElement("w:embedTrueTypeFonts")
        anchor = settings.find(qn("w:zoom"))
        if anchor is None:
            anchor = settings.find(qn("w:view"))
        if anchor is None:
            settings.insert(0, flag)
        else:
            anchor.addnext(flag)

    # -- content --------------------------------------------------------------
    def _runs(self, paragraph, text: str, block: Optional[Block] = None, offset: int = 0) -> None:
        for segment, tags in styled_segments(clean_xml_string(text), block.styles if block else [], offset):
            pieces = segment.split(BLANK_TOKEN)
            for index, piece in enumerate(pieces):
                if index:
                    blank = paragraph.add_run(" " * 12)
                    blank.font.underline = True
                lines = piece.split("\n")
                for line_index, line in enumerate(lines):
                    if line_index:
                        paragraph.add_run().add_break(WD_BREAK.LINE)
                    if not line:
                        continue
                    run = paragraph.add_run(line)
                    run.bold = True if "b" in tags else None
                    run.italic = True if "i" in tags else None
                    run.underline = True if "u" in tags else None

    def _direction(self, paragraph, block: Block) -> None:
        if block.text_direction != TextDirection.RTL:
            return
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _place(paragraph._p.get_or_add_pPr(), OxmlElement("w:bidi"), _PPR_ORDER)
        for run in paragraph.runs:
            _place(run._r.get_or_add_rPr(), OxmlElement("w:rtl"), _RPR_ORDER)

    def _note_paragraph(self, text: str) -> None:
        self._document.add_paragraph(clean_xml_string(text), style="Reader Note")

    def _picture(self, path: str, width_pt: float, height_pt: float, alt: str, align=WD_ALIGN_PARAGRAPH.CENTER) -> None:
        if self._options.monochrome:
            path = self._mono(path)
        paragraph = self._document.add_paragraph()
        paragraph.alignment = align
        run = paragraph.add_run()
        shape = run.add_picture(path, width=Emu(int(width_pt * 12700)), height=Emu(int(height_pt * 12700)))
        doc_pr = shape._inline.find(qn("wp:docPr"))
        if doc_pr is not None:
            doc_pr.set("descr", clean_xml_string(alt))

    @staticmethod
    def _mono(path: str) -> str:
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

    def _notes(self, block: Block) -> None:
        note = reader_note(block)
        if note:
            self._note_paragraph(note)
        asset = block.image_asset
        if has_original_crop(block) and asset.file_path and Path(asset.file_path).exists():
            w, h = picture_size(block, self._width.pt, self._height.pt, self._options.body_pt)
            self._picture(asset.file_path, w, h, f"The original lines from page {block.source_page}",
                          WD_ALIGN_PARAGRAPH.LEFT)

    def _block(self, block: Block) -> None:
        document = self._document
        b = self._options.body_pt
        if block.type == BlockType.PAGE_MARKER:
            if not self._options.include_page_markers or block.page_marker is None:
                return
            if self._options.page_break_on_source_page and block.page_marker > 1:
                document.add_page_break()
            label = page_label(block.page_marker, self._pages.get(block.page_marker))
            document.add_paragraph(label, style="Original Page")
            return
        if block.type in (BlockType.TITLE, BlockType.HEADING):
            level = 1 if block.type == BlockType.TITLE else max(1, min(3, block.level or 2))
            paragraph = document.add_paragraph(style=f"Heading {level}")
            self._runs(paragraph, block.text or "", block)
            self._direction(paragraph, block)
            return
        if block.type == BlockType.LIST:
            marker, rest = split_marker(block)
            paragraph = document.add_paragraph(style="List Item")
            fmt = paragraph.paragraph_format
            indent = block.indent_level * b * 1.7
            if marker:
                hang = max(b * 1.7, len(marker) * b * 0.6 + b * 0.6)
                fmt.left_indent = Pt(indent + hang)
                fmt.first_line_indent = Pt(-hang)
                fmt.tab_stops.add_tab_stop(Pt(indent + hang))
                run = paragraph.add_run(clean_xml_string(marker) + "\t")
                if block.role == "dialogue":
                    run.bold = True
                self._runs(paragraph, rest, block, len(block.text or "") - len(rest))
            else:
                fmt.left_indent = Pt(indent)
                self._runs(paragraph, block.text or "", block)
            self._direction(paragraph, block)
            self._notes(block)
            return
        if block.type == BlockType.CAPTION:
            paragraph = document.add_paragraph(style="Caption")
            label = caption_label(block)
            if label:
                paragraph.add_run(label).bold = True
            self._runs(paragraph, block.text or "", block)
            self._direction(paragraph, block)
            return
        if block.type == BlockType.QUOTE:
            paragraph = document.add_paragraph(style="Quote")
            self._runs(paragraph, block.text or "", block)
            self._direction(paragraph, block)
            self._notes(block)
            return
        if block.type == BlockType.FOOTNOTE:
            paragraph = document.add_paragraph(style="Footnote Text")
            self._runs(paragraph, block.text or "", block)
            self._direction(paragraph, block)
            return
        if block.type == BlockType.ASIDE:
            style = "Reader Note" if block.role == "page_note" else "Boxed Note"
            paragraph = document.add_paragraph(style=style)
            self._runs(paragraph, block.text or "", block)
            self._direction(paragraph, block)
            return
        if block.type == BlockType.TABLE and block.table_structure:
            self._table(block)
            return
        if block.type == BlockType.IMAGE and block.image_asset:
            asset = block.image_asset
            if not asset.file_path or not Path(asset.file_path).exists():
                return
            retained = is_retained_page(block)
            if retained:
                note = reader_note(block)
                if note:
                    self._note_paragraph(note)
            w, h = picture_size(block, self._width.pt, self._height.pt, b, retained=retained)
            self._picture(asset.file_path, w, h, asset.alt_text or f"Picture from page {block.source_page}")
            return
        paragraph = document.add_paragraph()
        self._runs(paragraph, block.text or "", block)
        self._direction(paragraph, block)
        self._notes(block)

    def _table(self, block: Block) -> None:
        table = block.table_structure
        b = self._options.body_pt
        cell_pt = max(14.0, b * 0.88)
        fit = evaluate_table_fit(table, available_width=self._width.pt, font_pt=cell_pt, min_readable_pt=14.0)
        for note in dict.fromkeys(n for n in (reader_note(block), fit.warning) if n):
            self._note_paragraph(note)
        if block.image_asset and block.image_asset.file_path and Path(block.image_asset.file_path).exists():
            w, h = picture_size(block, self._width.pt, self._height.pt, b)
            self._picture(block.image_asset.file_path, w, h,
                          block.image_asset.alt_text or f"Original table from page {block.source_page}")
        def caption(text: Optional[str]) -> None:
            if text:
                paragraph = self._document.add_paragraph(style="Caption")
                paragraph.paragraph_format.keep_with_next = True
                self._runs(paragraph, text)
                self._direction(paragraph, block)

        if fit.tier == TableTier.LINEARIZE:
            caption(table.caption)
            for lead, details in table_as_entries(table):
                if lead:
                    paragraph = self._document.add_paragraph(style="List Item")
                    paragraph.paragraph_format.keep_with_next = True
                    paragraph.add_run(clean_xml_string(lead)).bold = True
                for label, value in details:
                    paragraph = self._document.add_paragraph(style="List Item")
                    paragraph.paragraph_format.left_indent = Pt(b * 1.4)
                    if label:
                        paragraph.add_run(clean_xml_string(label) + ": ").bold = True
                    self._runs(paragraph, value)
            return
        parts = fit.split_tables if fit.tier == TableTier.SPLIT and fit.split_tables else [table]
        for part in parts:
            widths = fit.column_widths if part is table and len(fit.column_widths or []) == part.column_count else None
            caption(part.caption)
            self._grid(part, block.text_direction, widths, cell_pt)
            self._document.add_paragraph().paragraph_format.space_after = Pt(b * 0.3)

    def _grid(self, table: TableStructure, direction: TextDirection, widths, cell_pt: float) -> None:
        columns = table.column_count
        if not columns or not table.rows:
            return
        grid = self._document.add_table(rows=len(table.rows), cols=columns)
        grid.alignment = WD_TABLE_ALIGNMENT.CENTER
        grid.style = self._document.styles["Table Grid"]
        if direction == TextDirection.RTL:
            _place(grid._tbl.tblPr, OxmlElement("w:bidiVisual"), _TBLPR_ORDER)
        visible = {(r, c): (rs, cs) for r, c, _, rs, cs in iter_visible_cells(table)}
        for (r, c), (rs, cs) in visible.items():
            if rs > 1 or cs > 1:
                grid.cell(r, c).merge(grid.cell(r + rs - 1, c + cs - 1))
        scale = 1.0
        if widths:
            scale = min(1.0, self._width.pt / max(1.0, sum(widths)))
        for r, row in enumerate(table.rows):
            header = r == 0 and table.has_header
            tr = grid.rows[r]._tr.get_or_add_trPr()
            if header:
                tr.append(OxmlElement("w:tblHeader"))
                tr.append(OxmlElement("w:cantSplit"))
            for c, cell_data in enumerate(row[:columns]):
                if (r, c) not in visible:
                    continue
                cell = grid.cell(r, c)
                if widths and c < len(widths):
                    cell.width = Pt(widths[c] * scale)
                if header:
                    shading = OxmlElement("w:shd")
                    shading.set(qn("w:val"), "clear")
                    shading.set(qn("w:color"), "auto")
                    shading.set(qn("w:fill"), "FFFFFF" if self._options.monochrome else "EDEDED")
                    cell._tc.get_or_add_tcPr().append(shading)
                paragraph = cell.paragraphs[0]
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.line_spacing = 1.2
                run = paragraph.add_run(clean_xml_string(cell_data.text))
                _set_size(run, cell_pt)
                run.bold = True if header else None
                if direction == TextDirection.RTL:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    _place(paragraph._p.get_or_add_pPr(), OxmlElement("w:bidi"), _PPR_ORDER)
