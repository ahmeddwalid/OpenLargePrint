"""Native DOCX importer normalizing into canonical DocumentIR (OFF-001, DOC-001, LANG-001)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import List, Optional

import docx
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image

from openlargeprint.importers.base import BaseImporter
from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    ImageAsset,
    PageClassification,
    PageMetadata,
    TableCell,
    TableStructure,
    TextDirection,
)
from openlargeprint.security import JobWorkspace, validate_image_dimensions
from openlargeprint.text.direction import detect_language, detect_text_direction


from openlargeprint.importers.base import BaseImporter, CancelCheck, CheckpointCallback, ProgressCallback


class DocxImporter(BaseImporter):
    """Imports Word (.docx) documents preserving structural hierarchy into DocumentIR."""

    def import_document(
        self,
        file_path: Path,
        workspace: JobWorkspace,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
        checkpoint_callback: Optional[CheckpointCallback] = None,
    ) -> DocumentIR:
        """Parse Word (.docx) document and return normalized DocumentIR."""
        path = Path(file_path).resolve()
        try:
            doc = docx.Document(path)
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX document: {e}") from e

        blocks: List[Block] = []
        current_page = 1
        img_counter = 0

        if progress_callback:
            progress_callback(1, 1, "extracting", f"Importing Word document — {path.name}")

        # Always start with page 1 marker
        blocks.append(
            Block(
                id=f"p{current_page}_marker",
                type=BlockType.PAGE_MARKER,
                page_marker=current_page,
                source_page=current_page,
                extraction_method=ExtractionMethod.NATIVE,
            )
        )

        # Iterate over body elements in sequential order to preserve document flow
        body_elements = list(doc.element.body)
        for elem_idx, child in enumerate(body_elements):
            if isinstance(child, CT_P):
                p = Paragraph(child, doc)
                page_break_occurred, p_blocks, img_counter = self._process_paragraph(
                    p, doc, workspace, current_page, elem_idx, img_counter
                )
                if page_break_occurred:
                    current_page += 1
                    blocks.append(
                        Block(
                            id=f"p{current_page}_marker",
                            type=BlockType.PAGE_MARKER,
                            page_marker=current_page,
                            source_page=current_page,
                            extraction_method=ExtractionMethod.NATIVE,
                        )
                    )
                blocks.extend(p_blocks)

            elif isinstance(child, CT_Tbl):
                tbl = Table(child, doc)
                tbl_block = self._process_table(tbl, current_page, elem_idx)
                if tbl_block:
                    blocks.append(tbl_block)

        # Process any separate footnotes part if present
        footnote_blocks = self._extract_separate_footnotes(doc, current_page)
        blocks.extend(footnote_blocks)

        # Build PageMetadata array
        pages: List[PageMetadata] = []
        for p_num in range(1, current_page + 1):
            pages.append(
                PageMetadata(
                    page_number=p_num,
                    width=595.28,  # A4 standard portrait points
                    height=841.89,
                    classification=PageClassification.NATIVE,
                )
            )

        doc_title = path.stem.replace("_", " ").title()
        # If first heading exists, use it as title
        for b in blocks:
            if b.type == BlockType.HEADING and b.text:
                doc_title = b.text
                break

        metadata = DocumentMetadata(
            title=doc_title,
            page_count=current_page,
            source_file_name=path.name,
        )

        return DocumentIR(
            schema_version="1.0.0",
            metadata=metadata,
            pages=pages,
            blocks=blocks,
        )

    def _process_paragraph(
        self,
        p: Paragraph,
        doc: docx.Document,
        workspace: JobWorkspace,
        current_page: int,
        elem_idx: int,
        img_counter: int,
    ) -> tuple[bool, List[Block], int]:
        """Process a paragraph, extracting images, headings, lists, quotes, or body text."""
        blocks: List[Block] = []
        page_break_occurred = False

        # 1. Check for hard page breaks (<w:br w:type="page"/>)
        page_breaks = p._p.xpath('.//w:br[@w:type="page"]')
        if page_breaks:
            page_break_occurred = True

        # 2. Extract embedded relationship images in paragraph runs
        blip_nodes = p._p.xpath(".//a:blip")
        for blip in blip_nodes:
            r_embed = blip.get(qn("r:embed"))
            if r_embed and r_embed in doc.part.related_parts:
                part = doc.part.related_parts[r_embed]
                try:
                    blob = part.blob
                    img_counter += 1
                    img_filename = f"docx_img_{img_counter}.png"
                    img_path = workspace.assets_dir / img_filename
                    img_path.write_bytes(blob)

                    with Image.open(img_path) as pil_img:
                        w, h = pil_img.size
                        validate_image_dimensions(w, h)

                    asset = ImageAsset(
                        asset_id=f"docx_asset_{img_counter}",
                        file_path=str(img_path),
                        width=w,
                        height=h,
                        mime_type="image/png",
                    )
                    blocks.append(
                        Block(
                            id=f"p{current_page}_img_{img_counter}",
                            type=BlockType.IMAGE,
                            image_asset=asset,
                            source_page=current_page,
                            extraction_method=ExtractionMethod.OFFICE_IMPORT,
                        )
                    )
                except Exception:
                    # Ignore unreadable or corrupt image blobs gracefully
                    pass

        # 3. Process paragraph text
        text = p.text.strip()
        if not text:
            return page_break_occurred, blocks, img_counter

        # Classify script and text direction (LANG-001)
        direction = detect_text_direction(text)
        lang = detect_language(text)
        # Check XML w:bidi
        if p._p.xpath(".//w:pPr/w:bidi") or p._p.xpath(".//w:rPr/w:rtl"):
            direction = TextDirection.RTL
            lang = "ar"

        style_name = (p.style.name or "").lower()

        # Classify block type
        block_id = f"p{current_page}_b{elem_idx}"

        # Heading classification
        heading_match = re.search(r"heading\s*(\d+)", style_name)
        if heading_match:
            level = min(6, max(1, int(heading_match.group(1))))
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.HEADING,
                    text=text,
                    level=level,
                    language=lang,
                    text_direction=direction,
                    source_page=current_page,
                    extraction_method=ExtractionMethod.NATIVE,
                )
            )
            return page_break_occurred, blocks, img_counter

        if "title" in style_name:
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.HEADING,
                    text=text,
                    level=1,
                    language=lang,
                    text_direction=direction,
                    source_page=current_page,
                    extraction_method=ExtractionMethod.NATIVE,
                )
            )
            return page_break_occurred, blocks, img_counter

        if "subtitle" in style_name:
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.HEADING,
                    text=text,
                    level=2,
                    language=lang,
                    text_direction=direction,
                    source_page=current_page,
                    extraction_method=ExtractionMethod.NATIVE,
                )
            )
            return page_break_occurred, blocks, img_counter

        # List classification
        has_num_pr = bool(p._p.xpath(".//w:pPr/w:numPr"))
        if "list" in style_name or has_num_pr or text.startswith(("•", "-", "*")):
            clean_text = text.lstrip("•-* \t")
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.LIST,
                    text=clean_text if clean_text else text,
                    language=lang,
                    text_direction=direction,
                    source_page=current_page,
                    extraction_method=ExtractionMethod.NATIVE,
                )
            )
            return page_break_occurred, blocks, img_counter

        # Quote classification
        if "quote" in style_name:
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.QUOTE,
                    text=text,
                    language=lang,
                    text_direction=direction,
                    source_page=current_page,
                    extraction_method=ExtractionMethod.NATIVE,
                )
            )
            return page_break_occurred, blocks, img_counter

        # Caption classification
        if "caption" in style_name or re.match(r"^(figure|table|جدول|شكل)\s*[:\d]", text, re.IGNORECASE):
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.CAPTION,
                    text=text,
                    language=lang,
                    text_direction=direction,
                    source_page=current_page,
                    extraction_method=ExtractionMethod.NATIVE,
                )
            )
            return page_break_occurred, blocks, img_counter

        # Footnote classification
        if "footnote" in style_name:
            blocks.append(
                Block(
                    id=block_id,
                    type=BlockType.FOOTNOTE,
                    text=text,
                    language=lang,
                    text_direction=direction,
                    source_page=current_page,
                    extraction_method=ExtractionMethod.NATIVE,
                )
            )
            return page_break_occurred, blocks, img_counter

        # Default: Body paragraph
        blocks.append(
            Block(
                id=block_id,
                type=BlockType.PARAGRAPH,
                text=text,
                language=lang,
                text_direction=direction,
                source_page=current_page,
                extraction_method=ExtractionMethod.NATIVE,
            )
        )
        return page_break_occurred, blocks, img_counter

    def _process_table(self, tbl: Table, current_page: int, elem_idx: int) -> Optional[Block]:
        """Convert python-docx Table into canonical TableStructure (TBL-001)."""
        if not tbl.rows:
            return None

        table_rows: List[List[TableCell]] = []
        is_rtl_table = False

        # Check table-level bidiVisual attribute (LANG-001)
        tblPr = tbl._tbl.tblPr
        if tblPr is not None and tblPr.find(qn("w:bidiVisual")) is not None:
            is_rtl_table = True

        for r_idx, row in enumerate(tbl.rows):
            cells_row: List[TableCell] = []
            # Check row-level tblHeader attribute
            trPr = row._tr.get_or_add_trPr()
            is_header_row = (r_idx == 0) or (trPr.find(qn("w:tblHeader")) is not None)

            for c_idx, cell in enumerate(row.cells):
                cell_text = cell.text.strip()
                cell_direction = detect_text_direction(cell_text)
                cell_lang = detect_language(cell_text)
                if cell_direction == TextDirection.RTL:
                    is_rtl_table = True

                cells_row.append(
                    TableCell(
                        text=cell_text,
                        is_header=is_header_row,
                    )
                )
            table_rows.append(cells_row)

        table_struct = TableStructure(
            has_header=True,
            rows=table_rows,
        )

        direction = TextDirection.RTL if is_rtl_table else TextDirection.LTR
        lang = "ar" if is_rtl_table else "en"

        return Block(
            id=f"p{current_page}_tbl_{elem_idx}",
            type=BlockType.TABLE,
            text=table_struct.to_markdown_table(),
            table_structure=table_struct,
            language=lang,
            text_direction=direction,
            source_page=current_page,
            extraction_method=ExtractionMethod.NATIVE,
        )

    def _extract_separate_footnotes(self, doc: docx.Document, current_page: int) -> List[Block]:
        """Extract footnotes from related footnotes.xml part if present."""
        blocks: List[Block] = []
        try:
            for rel in doc.part.related_parts.values():
                if "footnotes" in rel.partname:
                    root = rel.element
                    for fn in root.xpath(".//w:footnote"):
                        fn_type = fn.get(qn("w:type"))
                        if fn_type in ("separator", "continuationSeparator"):
                            continue
                        texts = [node.text for node in fn.xpath(".//w:t") if node.text]
                        combined = " ".join(texts).strip()
                        if combined:
                            direction = detect_text_direction(combined)
                            lang = detect_language(combined)
                            fn_id = fn.get(qn("w:id"), str(uuid.uuid4())[:8])
                            blocks.append(
                                Block(
                                    id=f"p{current_page}_fn_{fn_id}",
                                    type=BlockType.FOOTNOTE,
                                    text=combined,
                                    language=lang,
                                    text_direction=direction,
                                    source_page=current_page,
                                    extraction_method=ExtractionMethod.NATIVE,
                                )
                            )
        except Exception:
            pass

        return blocks
