"""Native PDF extraction with column reconstruction and provenance (PDF-002, PDF-006)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import pikepdf
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from openlargeprint.importers.base import BaseImporter
from openlargeprint.ir.models import (
    Block,
    BlockType,
    BoundingBox,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    ImageAsset,
    PageClassification,
    PageMetadata,
    TextDirection,
)
from openlargeprint.security.isolation import JobWorkspace, log_safe_info
from .classifier import classify_pdf_page
from .images import extract_lossless_images_for_page


@dataclass
class TextLine:
    text: str
    rect: Tuple[float, float, float, float]  # left, bottom, right, top
    font_size: float
    font_name: str
    is_bold: bool
    page_num: int

    @property
    def x0(self) -> float:
        return self.rect[0]

    @property
    def y0(self) -> float:
        return self.rect[1]

    @property
    def x1(self) -> float:
        return self.rect[2]

    @property
    def y1(self) -> float:
        return self.rect[3]

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


class NativePdfImporter(BaseImporter):
    """Extracts exact text and embedded images from native/born-digital PDFs without OCR (PDF-002)."""

    def import_document(self, file_path: Path, workspace: JobWorkspace) -> DocumentIR:
        """Parse native PDF and construct canonical DocumentIR."""
        log_safe_info(f"Opening PDF document for native extraction: {file_path.name}")
        pdf = pdfium.PdfDocument(file_path)
        pike_doc = pikepdf.open(file_path)

        page_count = len(pdf)
        pages_metadata: List[PageMetadata] = []
        all_blocks: List[Block] = []
        block_counter = 1

        try:
            for page_idx in range(page_count):
                page_num = page_idx + 1
                page = pdf[page_idx]

                # 1. Classify page diagnostics (PDF-001, PDF-007)
                page_meta = classify_pdf_page(page, page_num)
                pages_metadata.append(page_meta)

                # 2. Add source-page transition marker (OUT-005)
                marker_block = Block(
                    id=f"p{page_num}_marker",
                    type=BlockType.PAGE_MARKER,
                    source_page=page_num,
                    page_marker=page_num,
                    extraction_method=ExtractionMethod.NATIVE,
                    confidence=1.0,
                )
                all_blocks.append(marker_block)

                # 3. Extract lossless embedded images (IMG-001) & query image bounds (PDF-006)
                try:
                    pike_page = pike_doc.pages[page_idx]
                    images = extract_lossless_images_for_page(
                        pike_page, page_num, workspace.assets_dir
                    )
                    image_objs = list(page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]))

                    for idx, img in enumerate(images):
                        bbox = None
                        if idx < len(image_objs):
                            try:
                                l, b, r, t = image_objs[idx].get_bounds()
                                bbox = BoundingBox(x0=float(l), y0=float(b), x1=float(r), y1=float(t))
                            except Exception:
                                pass

                        img_block = Block(
                            id=f"p{page_num}_b{block_counter}",
                            type=BlockType.IMAGE,
                            source_page=page_num,
                            source_bounding_box=bbox,
                            extraction_method=ExtractionMethod.NATIVE,
                            image_asset=img,
                            confidence=1.0,
                        )
                        block_counter += 1
                        all_blocks.append(img_block)
                except Exception as e:
                    log_safe_info(f"Image extraction skipped on page {page_num}: {type(e).__name__}")

                # 4. If page is confirmed native (or mixed), extract native text
                if page_meta.classification in (PageClassification.NATIVE, PageClassification.MIXED):
                    textpage = page.get_textpage()
                    try:
                        raw_lines = self._extract_raw_lines(textpage, page_num)
                    finally:
                        textpage.close()

                    if raw_lines:
                        # Reconstruct multi-column reading order
                        ordered_lines = self._order_lines_by_layout(
                            raw_lines, page_meta.width, page_meta.height
                        )
                        # Form semantic blocks (headings, paragraphs, lists)
                        page_blocks = self._form_semantic_blocks(
                            ordered_lines, page_num, block_counter
                        )
                        block_counter += len(page_blocks)
                        all_blocks.extend(page_blocks)
                else:
                    # Non-native pages in Milestone 1: note warning
                    # (Scanned/broken pages will be handled by OCR engine in Milestone 2)
                    log_safe_info(
                        f"Page {page_num} is classified as {page_meta.classification.value}; "
                        "marked for review (Principle 3)"
                    )
                    warning_block = Block(
                        id=f"p{page_num}_b{block_counter}",
                        type=BlockType.PARAGRAPH,
                        text=f"[Page {page_num} is {page_meta.classification.value} - marked for review]",
                        source_page=page_num,
                        extraction_method=ExtractionMethod.NATIVE,
                        confidence=0.5,
                        warnings=[f"Non-native page format: {page_meta.classification.value}"],
                    )
                    block_counter += 1
                    all_blocks.append(warning_block)

        finally:
            pike_doc.close()
            pdf.close()

        metadata = DocumentMetadata(
            title=file_path.stem.replace("_", " "),
            source_file_name=file_path.name,
            page_count=page_count,
        )

        return DocumentIR(
            schema_version="1.0.0",
            metadata=metadata,
            pages=pages_metadata,
            blocks=all_blocks,
        )

    def _extract_raw_lines(self, textpage: pdfium.PdfTextPage, page_num: int) -> List[TextLine]:
        """Extract text rectangles with font metrics and coordinates from textpage."""
        rect_count = textpage.count_rects()
        lines: List[TextLine] = []

        for i in range(rect_count):
            rect = textpage.get_rect(i)
            text = textpage.get_text_bounded(*rect).strip()
            if not text:
                continue

            # Query font metrics from midpoint of rect
            mid_x = (rect[0] + rect[2]) / 2.0
            mid_y = (rect[1] + rect[3]) / 2.0
            char_idx = textpage.get_index(mid_x, mid_y, 10.0, 10.0)

            font_size = rect[3] - rect[1]
            font_name = "Helvetica"
            is_bold = False

            if char_idx >= 0:
                text_obj = textpage.get_textobj(char_idx)
                if text_obj:
                    font_size = float(text_obj.get_font_size())
                    font = text_obj.get_font()
                    if font:
                        font_name = font.get_base_name()
                        is_bold = "bold" in font_name.lower() or font.get_weight() > 500

            lines.append(
                TextLine(
                    text=text,
                    rect=rect,
                    font_size=font_size,
                    font_name=font_name,
                    is_bold=is_bold,
                    page_num=page_num,
                )
            )

        return lines

    def _order_lines_by_layout(
        self, lines: List[TextLine], page_width: float, page_height: float
    ) -> List[TextLine]:
        """Reconstruct proper reading order for multi-column or single-column pages."""
        if len(lines) <= 2:
            return sorted(lines, key=lambda l: -l.y1)

        mid_x = page_width / 2.0
        left_col: List[TextLine] = []
        right_col: List[TextLine] = []
        full_width: List[TextLine] = []

        # Analyze column distribution
        for line in lines:
            if line.x0 < mid_x * 0.85 and line.x1 > mid_x * 1.15:
                # Spans across center: full width
                full_width.append(line)
            elif line.x1 <= mid_x + 15:
                # Confined to left half
                left_col.append(line)
            elif line.x0 >= mid_x - 15:
                # Confined to right half
                right_col.append(line)
            else:
                full_width.append(line)

        # Multi-column check: both columns must have substantial lines
        is_two_column = len(left_col) >= 2 and len(right_col) >= 2
        if not is_two_column:
            # Single column: sort strictly top-to-bottom (descending Y in PDF coordinates)
            return sorted(lines, key=lambda l: -l.y1)

        # In two-column mode:
        # 1. Full-width top headers
        # 2. Left column (top-to-bottom)
        # 3. Right column (top-to-bottom)
        # 4. Full-width bottom footers / notes
        col_top = max(max(l.y1 for l in left_col), max(l.y1 for l in right_col))
        col_bottom = min(min(l.y0 for l in left_col), min(l.y0 for l in right_col))

        top_headers = [l for l in full_width if l.y0 >= col_top - 5]
        bottom_footers = [l for l in full_width if l.y1 <= col_bottom + 5]
        middle_full = [l for l in full_width if l not in top_headers and l not in bottom_footers]

        ordered: List[TextLine] = []
        ordered.extend(sorted(top_headers, key=lambda l: -l.y1))
        ordered.extend(sorted(left_col, key=lambda l: -l.y1))
        ordered.extend(sorted(right_col, key=lambda l: -l.y1))
        ordered.extend(sorted(middle_full, key=lambda l: -l.y1))
        ordered.extend(sorted(bottom_footers, key=lambda l: -l.y1))

        return ordered

    def _form_semantic_blocks(
        self, lines: List[TextLine], page_num: int, start_idx: int
    ) -> List[Block]:
        """Cluster ordered lines into paragraphs, headings, and lists (DOC-002, PDF-006)."""
        if not lines:
            return []

        # Find median/typical body font size
        font_sizes = sorted(l.font_size for l in lines)
        body_font_size = font_sizes[len(font_sizes) // 2]

        blocks: List[Block] = []
        current_lines: List[TextLine] = []
        current_type = BlockType.PARAGRAPH
        current_level: Optional[int] = None
        idx = start_idx

        def flush_block():
            nonlocal idx, current_lines, current_type, current_level
            if not current_lines:
                return

            text_content = " ".join(l.text for l in current_lines)
            # Compute union bounding box
            min_x = min(l.x0 for l in current_lines)
            min_y = min(l.y0 for l in current_lines)
            max_x = max(l.x1 for l in current_lines)
            max_y = max(l.y1 for l in current_lines)
            bbox = BoundingBox(x0=min_x, y0=min_y, x1=max_x, y1=max_y)

            blk = Block(
                id=f"p{page_num}_b{idx}",
                type=current_type,
                text=text_content,
                level=current_level,
                source_page=page_num,
                source_bounding_box=bbox,
                extraction_method=ExtractionMethod.NATIVE,
                confidence=1.0,
            )
            blocks.append(blk)
            idx += 1
            current_lines = []
            current_type = BlockType.PARAGRAPH
            current_level = None

        for line in lines:
            # Check for heading
            is_heading = False
            heading_level = None

            if line.font_size >= 1.5 * body_font_size:
                is_heading = True
                heading_level = 1
            elif line.font_size >= 1.25 * body_font_size:
                is_heading = True
                heading_level = 2
            elif line.is_bold and len(line.text) < 80 and not line.text.endswith("."):
                is_heading = True
                heading_level = 3

            # Check for list item
            is_list_item = line.text.startswith(("- ", "* ", "• ", "\u2022 ", "\u25e6 ")) or (
                len(line.text) > 3 and line.text[0].isdigit() and line.text[1:3] in (". ", ") ")
            )

            if is_heading:
                flush_block()
                current_type = BlockType.HEADING
                current_level = heading_level
                current_lines.append(line)
                flush_block()
            elif is_list_item:
                flush_block()
                current_type = BlockType.LIST
                current_lines.append(line)
                flush_block()
            else:
                # Regular paragraph text: check continuity
                if current_lines:
                    prev = current_lines[-1]
                    # Check vertical distance
                    gap = prev.y0 - line.y1
                    same_column = abs(prev.x0 - line.x0) < 50
                    if gap > 2.0 * prev.height or not same_column:
                        # New paragraph
                        flush_block()
                current_lines.append(line)

        flush_block()
        return blocks
