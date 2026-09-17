"""Unified PDF extraction with automatic routing across native, scanned, and mixed pages (PDF-001..007)."""

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
from openlargeprint.ocr.base import DocumentOcrEngine
from openlargeprint.ocr.router import OcrRouter, RoutingMode
from openlargeprint.security.isolation import JobWorkspace, log_safe_info
from .classifier import classify_pdf_page
from .images import extract_lossless_images_for_page
from .scanned import ScannedPageExtractor


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
    """Imports PDF documents, dynamically routing pages across native extraction, OCR, and mixed reconciliation (DOC-001, PDF-001..007)."""

    def __init__(
        self,
        ocr_engine: Optional[DocumentOcrEngine] = None,
        routing_mode: RoutingMode = RoutingMode.AUTOMATIC,
        ocr_dpi: float = 200.0,
    ):
        self.routing_mode = routing_mode
        self.ocr_dpi = ocr_dpi
        self._router = OcrRouter()
        self.ocr_engine = ocr_engine or self._router.get_engine(routing_mode)
        self.scanned_extractor = ScannedPageExtractor(self.ocr_engine, dpi=ocr_dpi)

    def import_document(self, file_path: Path, workspace: JobWorkspace) -> DocumentIR:
        """Parse PDF and construct canonical DocumentIR."""
        log_safe_info(f"Opening PDF document: {file_path.name}")
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

                        # On a scanned page, do not treat full-page scan background as an inline figure
                        is_scanned_background = (
                            page_meta.classification == PageClassification.SCANNED
                            and bbox is not None
                            and (bbox.width * bbox.height) / (page_meta.width * page_meta.height) > 0.80
                        )

                        if not is_scanned_background:
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

                # 4. Route page processing according to classification (PDF-001..005)
                if page_meta.classification == PageClassification.NATIVE:
                    # Native extraction path (PDF-002: no OCR on native text)
                    page_blocks = self._extract_native_text(page, page_num, block_counter, page_meta)
                    block_counter += len(page_blocks)
                    all_blocks.extend(page_blocks)

                elif page_meta.classification in (PageClassification.SCANNED, PageClassification.BROKEN_DIGITAL):
                    # OCR path for scanned pages and broken-digital fallback (PDF-003, PDF-005)
                    log_safe_info(
                        f"Page {page_num} routed to OCR engine ({page_meta.classification.value})"
                    )
                    ocr_blocks = self.scanned_extractor.extract_page(page, page_num, block_counter)
                    block_counter += len(ocr_blocks)
                    all_blocks.extend(ocr_blocks)

                elif page_meta.classification == PageClassification.MIXED:
                    # Mixed page reconciliation path (PDF-004)
                    log_safe_info(f"Page {page_num} routed to mixed reconciliation (PDF-004)")
                    mixed_blocks = self._reconcile_mixed_page(page, page_num, block_counter, page_meta)
                    block_counter += len(mixed_blocks)
                    all_blocks.extend(mixed_blocks)

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

    def _reconcile_mixed_page(
        self,
        page: pdfium.PdfPage,
        page_num: int,
        start_idx: int,
        page_meta: PageMetadata,
    ) -> List[Block]:
        """Reconcile native text with selective OCR of regions lacking native text, deduplicating overlaps (PDF-004)."""
        # 1. Native text extraction
        native_blocks = self._extract_native_text(page, page_num, start_idx, page_meta)
        idx_after_native = start_idx + len(native_blocks)

        # 2. Run OCR over entire page
        ocr_blocks = self.scanned_extractor.extract_page(page, page_num, idx_after_native)

        # 3. Deduplicate: keep only OCR blocks that DO NOT overlap native text (Principle 1)
        accepted_ocr_blocks: List[Block] = []
        for ocr_b in ocr_blocks:
            if not ocr_b.source_bounding_box:
                continue
            ocr_box = ocr_b.source_bounding_box

            overlaps_native = False
            for nat_b in native_blocks:
                if not nat_b.source_bounding_box:
                    continue
                nat_box = nat_b.source_bounding_box

                # Check bounding box overlap
                x_overlap = max(0.0, min(ocr_box.x1, nat_box.x1) - max(ocr_box.x0, nat_box.x0))
                y_overlap = max(0.0, min(ocr_box.y1, nat_box.y1) - max(ocr_box.y0, nat_box.y0))
                overlap_area = x_overlap * y_overlap
                ocr_area = max(1.0, ocr_box.width * ocr_box.height)

                if (overlap_area / ocr_area) > 0.25:
                    overlaps_native = True
                    break

            if not overlaps_native:
                accepted_ocr_blocks.append(ocr_b)

        # 4. Merge native blocks and non-overlapping OCR blocks in reading order
        combined = native_blocks + accepted_ocr_blocks
        return sorted(
            combined,
            key=lambda b: (
                -(b.source_bounding_box.y1 if b.source_bounding_box else 0.0),
                (b.source_bounding_box.x0 if b.source_bounding_box else 0.0),
            ),
        )

    def _extract_native_text(
        self,
        page: pdfium.PdfPage,
        page_num: int,
        start_idx: int,
        page_meta: PageMetadata,
    ) -> List[Block]:
        """Extract native text spans, order columns, and form semantic blocks."""
        textpage = page.get_textpage()
        try:
            raw_lines = self._extract_raw_lines(textpage, page_num)
        finally:
            textpage.close()

        if not raw_lines:
            return []

        ordered_lines = self._order_lines_by_layout(raw_lines, page_meta.width, page_meta.height)
        return self._form_semantic_blocks(ordered_lines, page_num, start_idx)

    def _extract_raw_lines(self, textpage: pdfium.PdfTextPage, page_num: int) -> List[TextLine]:
        """Extract text rectangles with font metrics and coordinates from textpage."""
        rect_count = textpage.count_rects()
        lines: List[TextLine] = []

        for i in range(rect_count):
            rect = textpage.get_rect(i)
            text = textpage.get_text_bounded(*rect).strip()
            if not text:
                continue

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

        for line in lines:
            if line.x0 < mid_x * 0.85 and line.x1 > mid_x * 1.15:
                full_width.append(line)
            elif line.x1 <= mid_x + 15:
                left_col.append(line)
            elif line.x0 >= mid_x - 15:
                right_col.append(line)
            else:
                full_width.append(line)

        is_two_column = len(left_col) >= 2 and len(right_col) >= 2
        if not is_two_column:
            return sorted(lines, key=lambda l: -l.y1)

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
                if current_lines:
                    prev = current_lines[-1]
                    gap = prev.y0 - line.y1
                    same_column = abs(prev.x0 - line.x0) < 50
                    if gap > 2.0 * prev.height or not same_column:
                        flush_block()
                current_lines.append(line)

        flush_block()
        return blocks
