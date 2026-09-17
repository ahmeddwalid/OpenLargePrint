"""Large-print DOCX exporter (OUT-001, OUT-005..009)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor

from openlargeprint.ir.models import Block, BlockType, DocumentIR, TextDirection
from openlargeprint.security.isolation import log_safe_info
from .base import BaseExporter, ExportOptions, PaperSize, PresetName


class DocxExporter(BaseExporter):
    """Renders DocumentIR into an accessible, single-column large-print DOCX file."""

    def export(self, doc: DocumentIR, output_path: Path, options: Optional[ExportOptions] = None) -> Path:
        """Render DocumentIR into target large-print DOCX file."""
        if options is None:
            options = ExportOptions()

        log_safe_info(
            f"Exporting DocumentIR to DOCX at {options.body_pt}pt ({options.paper_size.value}) -> {output_path.name}"
        )

        document = docx.Document()
        section = document.sections[0]

        # 1. Physical page dimensions & margins (OUT-007..009)
        self._configure_page_geometry(section, options)

        # 2. Add print reminder notice (OUT-009)
        core_props = document.core_properties
        core_props.title = doc.metadata.title or "OpenLargePrint Document"
        core_props.comments = (
            f"OpenLargePrint output: {options.body_pt}pt text, {options.paper_size.value} paper size. "
            "REMINDER: Print at 100% / actual size rather than 'fit to page' to preserve text size."
        )

        # 3. Render blocks sequentially in single-column reflow
        usable_width = section.page_width - section.left_margin - section.right_margin

        for block in doc.blocks:
            self._render_block(document, block, options, usable_width)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output_path))
        log_safe_info(f"DOCX export completed successfully: {output_path.name}")
        return output_path

    def _configure_page_geometry(self, section: docx.section.Section, options: ExportOptions) -> None:
        """Set true physical page dimensions and proportional margins (OUT-007..009)."""
        if options.paper_size == PaperSize.A3:
            section.page_width = Mm(297)
            section.page_height = Mm(420)
            section.top_margin = Mm(25)
            section.bottom_margin = Mm(25)
            section.left_margin = Mm(25)
            section.right_margin = Mm(25)
        else:
            # Default A4
            section.page_width = Mm(210)
            section.page_height = Mm(297)
            section.top_margin = Mm(20)
            section.bottom_margin = Mm(20)
            section.left_margin = Mm(20)
            section.right_margin = Mm(20)

    def _render_block(
        self,
        document: docx.Document,
        block: Block,
        options: ExportOptions,
        usable_width: Inches,
    ) -> None:
        """Render an individual semantic block to DOCX according to typography preset."""
        # Handle page markers (OUT-005)
        if block.type == BlockType.PAGE_MARKER:
            if options.include_page_markers and block.page_marker is not None:
                p = document.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(options.body_pt * 0.8)
                p.paragraph_format.space_after = Pt(options.body_pt * 0.5)
                run = p.add_run(f"— Original Page {block.page_marker} —")
                run.font.name = options.font_family
                run.font.size = Pt(max(12.0, options.body_pt * 0.7))
                run.font.bold = True
                run.font.color.rgb = RGBColor(90, 90, 90)
            return

        # Handle headings
        if block.type in (BlockType.TITLE, BlockType.HEADING):
            level = block.level or 1
            p = document.add_paragraph()
            
            if level == 1:
                size_pt = max(26.0, options.body_pt * 1.4)
                p.paragraph_format.space_before = Pt(20)
                p.paragraph_format.space_after = Pt(10)
            elif level == 2:
                size_pt = max(23.0, options.body_pt * 1.25)
                p.paragraph_format.space_before = Pt(16)
                p.paragraph_format.space_after = Pt(8)
            else:
                size_pt = max(21.0, options.body_pt * 1.15)
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(6)

            p.paragraph_format.keep_with_next = True
            run = p.add_run(block.text or "")
            run.font.name = options.font_family
            run.font.size = Pt(size_pt)
            run.font.bold = True
            run.font.color.rgb = RGBColor(20, 20, 20)
            self._apply_text_direction(p, run, block, options)
            return

        # Handle lists
        if block.type == BlockType.LIST:
            p = document.add_paragraph(style="List Bullet")
            p.paragraph_format.line_spacing = options.line_spacing
            p.paragraph_format.space_after = Pt(options.body_pt * 0.3)
            # Strip initial bullet if text already has one
            raw_text = (block.text or "").lstrip("•-* \t")
            run = p.add_run(raw_text)
            run.font.name = options.font_family
            run.font.size = Pt(options.body_pt)
            self._apply_text_direction(p, run, block, options)
            return

        # Handle quotes
        if block.type == BlockType.QUOTE:
            p = document.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.4)
            p.paragraph_format.line_spacing = options.line_spacing
            p.paragraph_format.space_after = Pt(options.body_pt * 0.5)
            run = p.add_run(block.text or "")
            run.font.name = options.font_family
            run.font.size = Pt(options.body_pt)
            run.font.italic = True
            self._apply_text_direction(p, run, block, options)
            return

        # Handle footnotes and captions (FN-002: enforce minimum readable size)
        if block.type in (BlockType.FOOTNOTE, BlockType.CAPTION):
            min_size = max(14.0, options.body_pt * 0.8)
            p = document.add_paragraph()
            p.paragraph_format.line_spacing = 1.3
            p.paragraph_format.space_after = Pt(8)
            run = p.add_run(block.text or "")
            run.font.name = options.font_family
            run.font.size = Pt(min_size)
            run.font.italic = True
            run.font.color.rgb = RGBColor(70, 70, 70)
            self._apply_text_direction(p, run, block, options)
            return

        # Handle images (IMG-001, IMG-003)
        if block.type == BlockType.IMAGE and block.image_asset:
            asset = block.image_asset
            if asset.file_path and Path(asset.file_path).exists():
                p = document.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(12)

                # Maintain aspect ratio (IMG-003)
                # Compute scaling to fit page width
                native_width = Inches(asset.width / 96.0)
                display_width = min(usable_width, native_width)

                p.add_run().add_picture(asset.file_path, width=display_width)
            return

        # Default: Regular body paragraph
        p = document.add_paragraph()
        p.paragraph_format.line_spacing = options.line_spacing
        p.paragraph_format.space_after = Pt(options.body_pt * 0.55)  # Generous paragraph spacing
        run = p.add_run(block.text or "")
        run.font.name = options.font_family
        run.font.size = Pt(options.body_pt)
        run.font.color.rgb = RGBColor(20, 20, 20)
        self._apply_text_direction(p, run, block, options)

    def _apply_text_direction(self, p, run, block: Block, options: ExportOptions) -> None:
        """Apply RTL paragraph alignment and OpenXML attributes if block is RTL (LANG-001)."""
        if block.text_direction == TextDirection.RTL:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pPr = p._p.get_or_add_pPr()
            if pPr.find(qn("w:bidi")) is None:
                pPr.append(OxmlElement("w:bidi"))

            rPr = run._r.get_or_add_rPr()
            if rPr.find(qn("w:rtl")) is None:
                rPr.append(OxmlElement("w:rtl"))

            # Complex script font for Arabic
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.append(rFonts)
            rFonts.set(qn("w:cs"), "Traditional Arabic")
            rFonts.set(qn("w:ascii"), options.font_family)
            rFonts.set(qn("w:hAnsi"), options.font_family)
