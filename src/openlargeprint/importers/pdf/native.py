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
    TableCell,
    TableStructure,
    TextDirection,
)
import re
from openlargeprint.ocr.base import DocumentOcrEngine
from openlargeprint.ocr.router import OcrRouter, RoutingMode
from openlargeprint.security.isolation import JobWorkspace, log_safe_info
from openlargeprint.text.direction import (
    detect_language,
    detect_text_direction,
    normalize_arabic_logical_order,
)
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
        routing_mode: RoutingMode = RoutingMode.MAXIMUM_ACCURACY,
        ocr_dpi: float = 300.0,
    ):
        self.routing_mode = routing_mode
        self.ocr_dpi = ocr_dpi
        self._router = OcrRouter()
        self.ocr_engine = ocr_engine or self._router.get_engine(routing_mode)
        self.scanned_extractor = ScannedPageExtractor(self.ocr_engine, dpi=ocr_dpi)

    def import_document(
        self,
        file_path: Path,
        workspace: JobWorkspace,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
        checkpoint_callback: Optional[CheckpointCallback] = None,
    ) -> DocumentIR:
        """Parse PDF and construct canonical DocumentIR with progress and checkpointing (UI-002, UI-003)."""
        log_safe_info(f"Opening PDF document: {file_path.name}")
        pdf = pdfium.PdfDocument(file_path)
        pike_doc = pikepdf.open(file_path)

        page_count = len(pdf)
        pages_metadata: List[PageMetadata] = []
        all_blocks: List[Block] = []
        block_counter = 1

        try:
            for page_idx in range(page_count):
                if cancel_check and cancel_check():
                    log_safe_info("Cancellation signal received during PDF import (UI-002)")
                    raise InterruptedError("Operation cancelled by user.")

                page_num = page_idx + 1
                page = pdf[page_idx]

                # 1. Classify page diagnostics (PDF-001, PDF-007)
                page_meta = classify_pdf_page(page, page_num)
                pages_metadata.append(page_meta)

                # Send real-time progress event (UI-002)
                if progress_callback:
                    stage = "ocr" if page_meta.classification in (PageClassification.SCANNED, PageClassification.BROKEN_DIGITAL) else "extracting"
                    msg = (
                        f"Recognizing scanned text — page {page_num} of {page_count}"
                        if stage == "ocr"
                        else f"Extracting digital text — page {page_num} of {page_count}"
                    )
                    progress_callback(page_num, page_count, stage, msg)

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

                page_blocks: List[Block] = []
                try:
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
                                page_blocks.append(img_block)
                    except Exception as e:
                        log_safe_info(f"Image extraction skipped on page {page_num}: {type(e).__name__}")

                    # 4. Route page processing according to classification (PDF-001..005)
                    if page_meta.classification == PageClassification.NATIVE:
                        # Native extraction path (PDF-002: no OCR on native text)
                        extracted = self._extract_native_text(page, page_num, block_counter, page_meta)
                        block_counter += len(extracted)
                        page_blocks.extend(extracted)

                    elif page_meta.classification in (PageClassification.SCANNED, PageClassification.BROKEN_DIGITAL):
                        # OCR path for scanned pages and broken-digital fallback (PDF-003, PDF-005)
                        log_safe_info(
                            f"Page {page_num} routed to OCR engine ({page_meta.classification.value})"
                        )
                        extracted = self.scanned_extractor.extract_page(page, page_num, block_counter)
                        block_counter += len(extracted)
                        page_blocks.extend(extracted)

                    elif page_meta.classification == PageClassification.MIXED:
                        # Mixed page reconciliation path (PDF-004)
                        log_safe_info(f"Page {page_num} routed to mixed reconciliation (PDF-004)")
                        extracted = self._reconcile_mixed_page(page, page_num, block_counter, page_meta)
                        block_counter += len(extracted)
                        page_blocks.extend(extracted)

                    all_blocks.extend(page_blocks)

                    # 5. Checkpoint callback per page (UI-003)
                    if checkpoint_callback:
                        has_warn = any(bool(b.warnings) for b in page_blocks)
                        warn_msg = None
                        if has_warn:
                            for b in page_blocks:
                                if b.warnings:
                                    warn_msg = b.warnings[0]
                                    break
                        checkpoint_callback(page_num, page_meta.classification, has_warn, warn_msg)

                except Exception as page_err:
                    # UI-003: Single failed page must not discard already-converted pages
                    log_safe_info(f"Page {page_num} encountered extraction error: {type(page_err).__name__}")
                    fallback_block = Block(
                        id=f"p{page_num}_err_fallback",
                        type=BlockType.PARAGRAPH,
                        text=f"[Original page {page_num} preserved for review]",
                        warnings=[f"Page {page_num} extraction failed: {str(page_err)}"],
                        source_page=page_num,
                        confidence=0.0,
                    )
                    all_blocks.append(fallback_block)
                    if checkpoint_callback:
                        checkpoint_callback(page_num, page_meta.classification, True, f"Page {page_num} extraction error")

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

        # 1. Detect and extract tables before column ordering (TBL-001)
        non_table_lines, table_blocks = self._extract_tables(raw_lines, page_num, start_idx, page_meta)
        idx_after_tables = start_idx + len(table_blocks)

        # 2. Reconstruct column order for regular text
        ordered_lines = self._order_lines_by_layout(non_table_lines, page_meta.width, page_meta.height)

        # 3. Form semantic blocks (headings, paragraphs, lists, footnotes, captions)
        text_blocks = self._form_semantic_blocks(
            ordered_lines, page_num, idx_after_tables, page_meta.height
        )

        # 4. If table blocks were extracted, insert them in reading order without
        # disrupting multi-column ordering of text_blocks
        if not table_blocks:
            return text_blocks

        all_blocks: List[Block] = []
        tbl_idx = 0
        sorted_tables = sorted(
            table_blocks,
            key=lambda b: -(b.source_bounding_box.y1 if b.source_bounding_box else 0.0),
        )
        for tb in text_blocks:
            tb_y = tb.source_bounding_box.y1 if tb.source_bounding_box else 0.0
            while tbl_idx < len(sorted_tables):
                curr_tbl = sorted_tables[tbl_idx]
                tbl_y = curr_tbl.source_bounding_box.y1 if curr_tbl.source_bounding_box else 0.0
                if tbl_y >= tb_y:
                    all_blocks.append(curr_tbl)
                    tbl_idx += 1
                else:
                    break
            all_blocks.append(tb)
        while tbl_idx < len(sorted_tables):
            all_blocks.append(sorted_tables[tbl_idx])
            tbl_idx += 1
        return all_blocks

    def _extract_tables(
        self,
        lines: List[TextLine],
        page_num: int,
        start_idx: int,
        page_meta: PageMetadata,
    ) -> Tuple[List[TextLine], List[Block]]:
        """Identify multi-column aligned grids and construct TableStructure blocks (TBL-001)."""
        if len(lines) < 4:
            return lines, []

        # 1. Group lines by horizontal row bands (similar y0 within 6pt tolerance)
        rows_by_y: List[List[TextLine]] = []
        sorted_by_y = sorted(lines, key=lambda l: -l.y0)

        for line in sorted_by_y:
            placed = False
            for r in rows_by_y:
                if abs(r[0].y0 - line.y0) <= 6.0 and abs(r[0].y1 - line.y1) <= 6.0:
                    r.append(line)
                    placed = True
                    break
            if not placed:
                rows_by_y.append([line])

        for r in rows_by_y:
            r.sort(key=lambda l: l.x0)

        # 2. Identify candidate multi-column rows (>= 2 cells separated by >= 8pt horizontal gap)
        multi_col_rows: List[Tuple[int, List[TextLine]]] = []
        for r_idx, r in enumerate(rows_by_y):
            if len(r) >= 2:
                has_gaps = all(r[i + 1].x0 - r[i].x1 >= 8.0 for i in range(len(r) - 1))
                if has_gaps:
                    multi_col_rows.append((r_idx, r))

        if len(multi_col_rows) < 2:
            return lines, []

        # 3. Find contiguous clusters of multi-column rows
        table_clusters: List[List[List[TextLine]]] = []
        curr_cluster: List[List[TextLine]] = []
        prev_r_idx = -99

        for r_idx, r in multi_col_rows:
            if curr_cluster and (r_idx - prev_r_idx > 2 or abs(len(r) - len(curr_cluster[-1])) > 1):
                if len(curr_cluster) >= 2:
                    table_clusters.append(curr_cluster)
                curr_cluster = []
            curr_cluster.append(r)
            prev_r_idx = r_idx

        if len(curr_cluster) >= 2:
            table_clusters.append(curr_cluster)

        if not table_clusters:
            return lines, []

        table_blocks: List[Block] = []
        consumed_line_ids: set[int] = set()
        idx = start_idx

        for cluster in table_clusters:
            all_x0s = sorted(l.x0 for r in cluster for l in r)
            col_anchors: List[float] = []
            for x in all_x0s:
                if not col_anchors or (x - col_anchors[-1] > 25.0):
                    col_anchors.append(x)

            if len(col_anchors) < 2:
                continue

            # Invariant: Disambiguate 2-column page layout from a table.
            # If there are only 2 columns, and both columns span wide portions of the page (> 30% page width each)
            # or lines are long (> 35 chars average), it is a 2-column page layout, NOT a table!
            if len(col_anchors) == 2:
                avg_len = sum(len(l.text) for r in cluster for l in r) / max(1, sum(len(r) for r in cluster))
                max_w = max((l.x1 - l.x0) for r in cluster for l in r)
                if avg_len > 35 or max_w > 0.30 * page_meta.width:
                    continue

            grid: List[List[TableCell]] = []
            all_cluster_lines: List[TextLine] = []

            for r_idx, row_lines in enumerate(cluster):
                row_cells: List[TableCell] = [
                    TableCell(text="", is_header=(r_idx == 0)) for _ in col_anchors
                ]
                for line in row_lines:
                    all_cluster_lines.append(line)
                    consumed_line_ids.add(id(line))
                    best_c = 0
                    min_dist = 9999.0
                    for c_idx, anchor in enumerate(col_anchors):
                        dist = abs(line.x0 - anchor)
                        if dist < min_dist:
                            min_dist = dist
                            best_c = c_idx
                    existing = row_cells[best_c].text
                    row_cells[best_c].text = (existing + " " + line.text).strip() if existing else line.text

                grid.append(row_cells)

            has_cells = any(any(c.text for c in row) for row in grid)
            if not has_cells:
                continue

            min_x = min(l.x0 for l in all_cluster_lines)
            min_y = min(l.y0 for l in all_cluster_lines)
            max_x = max(l.x1 for l in all_cluster_lines)
            max_y = max(l.y1 for l in all_cluster_lines)
            bbox = BoundingBox(x0=min_x, y0=min_y, x1=max_x, y1=max_y)

            table_struct = TableStructure(rows=grid, has_header=True)
            tbl_text = table_struct.to_markdown_table()
            tbl_lang = detect_language(tbl_text)
            tbl_dir = detect_text_direction(tbl_text)

            tbl_block = Block(
                id=f"p{page_num}_tbl{idx}",
                type=BlockType.TABLE,
                text=tbl_text,
                table_structure=table_struct,
                source_page=page_num,
                source_bounding_box=bbox,
                extraction_method=ExtractionMethod.NATIVE,
                confidence=1.0,
                language=tbl_lang,
                text_direction=tbl_dir,
            )
            table_blocks.append(tbl_block)
            idx += 1

        remaining_lines = [l for l in lines if id(l) not in consumed_line_ids]
        return remaining_lines, table_blocks

    def _extract_raw_lines(self, textpage: pdfium.PdfTextPage, page_num: int) -> List[TextLine]:
        """Extract text rectangles with font metrics and coordinates from textpage."""
        rect_count = textpage.count_rects()
        lines: List[TextLine] = []

        for i in range(rect_count):
            rect = textpage.get_rect(i)
            text = textpage.get_text_bounded(*rect).strip()
            if not text:
                continue

            # Normalize visual-order Arabic if needed
            text = normalize_arabic_logical_order(text)

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

        # Detect page text direction for multi-column ordering (PDF-003, LANG-002)
        sample_text = " ".join(l.text for l in lines)
        page_dir = detect_text_direction(sample_text)

        col_top = max(max(l.y1 for l in left_col), max(l.y1 for l in right_col))
        col_bottom = min(min(l.y0 for l in left_col), min(l.y0 for l in right_col))

        top_headers = [l for l in full_width if l.y0 >= col_top - 5]
        bottom_footers = [l for l in full_width if l.y1 <= col_bottom + 5]
        middle_full = [l for l in full_width if l not in top_headers and l not in bottom_footers]

        ordered: List[TextLine] = []
        ordered.extend(sorted(top_headers, key=lambda l: -l.y1))
        if page_dir == TextDirection.RTL:
            # In RTL scripts (Arabic), Column 1 is on the RIGHT, Column 2 is on the LEFT (LANG-002)
            ordered.extend(sorted(right_col, key=lambda l: -l.y1))
            ordered.extend(sorted(left_col, key=lambda l: -l.y1))
        else:
            ordered.extend(sorted(left_col, key=lambda l: -l.y1))
            ordered.extend(sorted(right_col, key=lambda l: -l.y1))
        ordered.extend(sorted(middle_full, key=lambda l: -l.y1))
        ordered.extend(sorted(bottom_footers, key=lambda l: -l.y1))
        return ordered

    def _form_semantic_blocks(
        self,
        lines: List[TextLine],
        page_num: int,
        start_idx: int,
        page_height: float = 792.0,
    ) -> List[Block]:
        """Cluster ordered lines into paragraphs, headings, lists, footnotes, and captions (DOC-002, PDF-006, FN-001)."""
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
            normalized_text = normalize_arabic_logical_order(text_content)
            blk_lang = detect_language(normalized_text)
            blk_dir = detect_text_direction(normalized_text)

            min_x = min(l.x0 for l in current_lines)
            min_y = min(l.y0 for l in current_lines)
            max_x = max(l.x1 for l in current_lines)
            max_y = max(l.y1 for l in current_lines)
            bbox = BoundingBox(x0=min_x, y0=min_y, x1=max_x, y1=max_y)

            blk = Block(
                id=f"p{page_num}_b{idx}",
                type=current_type,
                text=normalized_text,
                level=current_level,
                language=blk_lang,
                text_direction=blk_dir,
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
            # 1. Footnote detection (FN-001, FN-002)
            # Located in bottom 28% of page with footnote marker or smaller font
            is_at_page_bottom = line.y1 <= 0.28 * page_height
            is_smaller_font = line.font_size <= 0.92 * body_font_size
            starts_with_fn_marker = bool(
                re.match(r"^(?:\[\d+\]|\d+[\.\)]|\*|¹|²|³|†|‡|\d+\s+)", line.text)
            )
            is_footnote = is_at_page_bottom and (
                starts_with_fn_marker or (is_smaller_font and current_type == BlockType.FOOTNOTE)
            )

            # 2. Caption detection
            is_caption = bool(
                re.match(
                    r"^(?:Figure|Fig\.|Table|Exhibit|Illustration|جدول|شكل)\s+(?:\d+|[A-ZIVX]+)(?::|\.|\s-|\s—)",
                    line.text,
                    re.IGNORECASE,
                )
            )

            is_heading = False
            heading_level = None
            if not is_footnote and not is_caption:
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

            if is_footnote:
                if current_type != BlockType.FOOTNOTE or starts_with_fn_marker:
                    flush_block()
                    current_type = BlockType.FOOTNOTE
                current_lines.append(line)
            elif is_caption:
                flush_block()
                current_type = BlockType.CAPTION
                current_lines.append(line)
                flush_block()
            elif is_heading:
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
