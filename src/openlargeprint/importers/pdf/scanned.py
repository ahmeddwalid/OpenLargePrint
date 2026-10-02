"""Scanned PDF layout and OCR text extraction (PDF-003, PDF-006, OCR-004, OCR-005)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from openlargeprint.security.validator import bounded_pdf_scale
import re
import tempfile
from typing import Any, List, Optional, Tuple
import uuid
import pypdfium2 as pdfium
from PIL import ImageDraw

from openlargeprint.ir.models import (
    Block,
    BlockType,
    BoundingBox,
    ExtractionMethod,
    ImageAsset,
    TableCell,
    TableStructure,
    TextDirection,
)
from openlargeprint.ocr.base import CancellationToken, DocumentOcrEngine
from openlargeprint.ocr.router import RoutingMode
from openlargeprint.importers.base import CancelCheck
from openlargeprint.security.isolation import log_safe_info
from openlargeprint.text.direction import detect_language, detect_text_direction


@dataclass
class OcrPointLine:
    """An OCR line mapped into PDF point coordinates."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


class ScannedPageExtractor:
    """Renders scanned PDF pages, invokes OCR, reconstructs columns, and yields DocumentIR blocks."""

    def __init__(
        self,
        ocr_engine: DocumentOcrEngine,
        dpi: float = 300.0,
        ocr_router: Optional[Any] = None,
        routing_mode: RoutingMode = RoutingMode.AUTOMATIC,
    ):
        self.ocr_engine = ocr_engine
        self.dpi = dpi
        self.ocr_router = ocr_router
        self.routing_mode = routing_mode

    def extract_page(
        self,
        page: pdfium.PdfPage,
        page_num: int,
        start_block_idx: int,
        assets_dir: Optional[Path] = None,
        cancel_check: Optional[CancelCheck] = None,
        native_regions: Optional[List[Tuple[float, float, float, float]]] = None,
        language_hints: Tuple[str, ...] = ("en",),
    ) -> List[Block]:
        """Render page, perform OCR recognition, reconstruct columns, and form semantic blocks."""
        page_w_pt, page_h_pt = page.get_size()
        scale = bounded_pdf_scale(page_w_pt, page_h_pt, self.dpi)

        # 1. Render page bitmap at OCR resolution (PDF-003)
        bitmap = page.render(scale=scale)
        pil_img = bitmap.to_pil()

        try:
            if native_regions:
                draw = ImageDraw.Draw(pil_img)
                for left, bottom, right, top in native_regions:
                    draw.rectangle(
                        (left * scale, (page_h_pt - top) * scale,
                         right * scale, (page_h_pt - bottom) * scale),
                        fill="white",
                    )
            # 2. Run OCR recognition (OCR-001, OCR-002, OCR-006)
            engine = self.ocr_engine
            if self.ocr_router is not None:
                engine = self.ocr_router.get_engine(
                    self.routing_mode, language=language_hints[0] if language_hints else "en"
                )
            import inspect
            sig = inspect.signature(engine.analyze_page)
            analyze_kwargs = {
                "page_num": page_num,
                "cancellation": CancellationToken(cancel_check),
            }
            if "language_hints" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                analyze_kwargs["language_hints"] = language_hints

            ocr_res = engine.analyze_page(pil_img, **analyze_kwargs)
            if ocr_res.cancelled or (cancel_check and cancel_check()):
                raise InterruptedError("Conversion cancelled.")
            log_safe_info(
                f"Page {page_num} OCR recognized {len(ocr_res.lines)} lines in {ocr_res.elapse_seconds:.2f}s"
            )

            if not ocr_res.lines:
                if native_regions:
                    return []
                # Handle empty page detection (OCR-005)
                return [
                    Block(
                        id=f"p{page_num}_b{start_block_idx}",
                        type=BlockType.PARAGRAPH,
                        text=f"[Page {page_num}: No text recognized on scanned page]",
                        source_page=page_num,
                        extraction_method=ExtractionMethod.OCR_FAST,
                        confidence=0.0,
                        warnings=["OCR produced no text for scanned page"],
                    )
                ]

            # 3. Transform pixel coordinates to PDF point coordinates (PDF-006)
            point_lines: List[OcrPointLine] = []
            for line in ocr_res.lines:
                x0_pt = line.x0 / scale
                x1_pt = line.x1 / scale
                # Invert Y: pixel 0 is at top, PDF 0 is at bottom
                y1_pt = page_h_pt - (line.y0 / scale)
                y0_pt = page_h_pt - (line.y1 / scale)
                point_lines.append(
                    OcrPointLine(
                        text=line.text,
                        x0=x0_pt,
                        y0=y0_pt,
                        x1=x1_pt,
                        y1=y1_pt,
                        confidence=line.confidence,
                    )
                )

            # 4. Detect and extract tables before column ordering (TBL-001)
            non_table_lines, table_blocks = self._extract_tables(
                point_lines, page_num, start_block_idx, page_w_pt, page_h_pt, pil_img, scale, assets_dir
            )
            idx_after_tables = start_block_idx + len(table_blocks)

            # 5. Reconstruct multi-column reading order (PDF-003)
            ordered_lines = self._order_lines_by_columns(non_table_lines, page_w_pt, page_h_pt)

            # 6. Form semantic blocks with confidence and warnings (OCR-004, OCR-005, FN-001)
            text_blocks = self._cluster_semantic_blocks(
                ordered_lines, page_num, idx_after_tables, ocr_res.warnings, page_h_pt
            )

            # Keep content order from the column pass; insert graphics within
            # the matching column rather than globally re-sorting the page.
            graphic_blocks = []
            if assets_dir is not None:
                from .figures import extract_scanned_figures
                occupied = [(line.x0, line.y0, line.x1, line.y1) for line in ocr_res.lines]
                for table in table_blocks:
                    box = table.source_bounding_box
                    occupied.append((box.x0 * scale, (page_h_pt - box.y1) * scale,
                                     box.x1 * scale, (page_h_pt - box.y0) * scale))
                graphic_blocks = extract_scanned_figures(pil_img, occupied, page_num, scale, assets_dir)
            merged = list(text_blocks)
            for extra in sorted(table_blocks + graphic_blocks, key=lambda b: -b.source_bounding_box.y1):
                box = extra.source_bounding_box
                position = len(merged)
                for index, block in enumerate(merged):
                    other = block.source_bounding_box
                    if other and min(box.x1, other.x1) > max(box.x0, other.x0) and box.y1 >= other.y1:
                        position = index
                        break
                merged.insert(position, extra)
            return merged
        finally:
            pil_img.close()
            bitmap.close()

    def _order_lines_by_columns(
        self, lines: List[OcrPointLine], page_w: float, page_h: float, _depth: int = 0
    ) -> List[OcrPointLine]:
        """Reconstruct proper reading order for single- or multi-column scanned pages using adaptive gutters and vertical banding."""
        if len(lines) <= 2 or _depth >= 16:
            return sorted(lines, key=lambda l: -l.y1)

        # 1. Adaptive Gutter Detection
        body_lines = [l for l in lines if (l.x1 - l.x0) < 0.65 * page_w and len(l.text.strip()) > 0]
        split_x = (min(l.x0 for l in lines) + max(l.x1 for l in lines)) / 2 if _depth else page_w / 2.0
        is_multi_col = False

        if len(body_lines) >= 4:
            start_x = int(max(0.25 * page_w, min(l.x0 for l in body_lines) + 2))
            end_x = int(min(0.75 * page_w, max(l.x1 for l in body_lines) - 2))
            if _depth:
                start_x = int(min(l.x0 for l in body_lines) + 2)
                end_x = int(max(l.x1 for l in body_lines) - 2)
            best_gutter_center = page_w / 2.0
            best_gutter_width = 0.0
            current_gutter_start = None

            for x in range(start_x, end_x, 2):
                crossing = sum(1 for l in body_lines if l.x0 <= x <= l.x1)
                if crossing == 0:
                    if current_gutter_start is None:
                        current_gutter_start = x
                else:
                    if current_gutter_start is not None:
                        gutter_w = x - current_gutter_start
                        if gutter_w > best_gutter_width:
                            best_gutter_width = gutter_w
                            best_gutter_center = (current_gutter_start + x) / 2.0
                        current_gutter_start = None

            if current_gutter_start is not None:
                gutter_w = end_x - current_gutter_start
                if gutter_w > best_gutter_width:
                    best_gutter_width = gutter_w
                    best_gutter_center = (current_gutter_start + end_x) / 2.0

            if best_gutter_width >= 8.0:
                left_count = sum(1 for l in body_lines if l.x1 <= best_gutter_center + 10)
                right_count = sum(1 for l in body_lines if l.x0 >= best_gutter_center - 10)
                if left_count >= 2 and right_count >= 2:
                    split_x = best_gutter_center
                    is_multi_col = True

        if not is_multi_col:
            # Fallback to midpoint test
            left_count = sum(1 for l in body_lines if l.x1 <= split_x + 15)
            right_count = sum(1 for l in body_lines if l.x0 >= split_x - 15)
            if left_count >= 2 and right_count >= 2:
                is_multi_col = True

        if not is_multi_col:
            return sorted(lines, key=lambda l: -l.y1)

        # 2. Multi-column classification
        sample_text = " ".join(l.text for l in lines)
        page_dir = detect_text_direction(sample_text)

        left_lines: List[OcrPointLine] = []
        right_lines: List[OcrPointLine] = []
        full_width_breaks: List[OcrPointLine] = []

        for line in lines:
            if line.x0 < split_x * 0.85 and line.x1 > split_x * 1.15:
                full_width_breaks.append(line)
            elif line.x1 <= split_x + 15:
                left_lines.append(line)
            elif line.x0 >= split_x - 15:
                right_lines.append(line)
            else:
                full_width_breaks.append(line)

        full_width_breaks.sort(key=lambda l: -l.y1)

        # 3. Vertical banding: full-width lines act as section dividers
        ordered: List[OcrPointLine] = []
        if not full_width_breaks:
            if page_dir == TextDirection.RTL:
                ordered.extend(self._order_lines_by_columns(right_lines, page_w, page_h, _depth + 1))
                ordered.extend(self._order_lines_by_columns(left_lines, page_w, page_h, _depth + 1))
            else:
                ordered.extend(self._order_lines_by_columns(left_lines, page_w, page_h, _depth + 1))
                ordered.extend(self._order_lines_by_columns(right_lines, page_w, page_h, _depth + 1))
            return ordered

        remaining_left = list(left_lines)
        remaining_right = list(right_lines)

        for fw in full_width_breaks:
            fw_bottom = fw.y0
            band_left = [l for l in remaining_left if l.y0 >= fw_bottom - 4.0]
            band_right = [l for l in remaining_right if l.y0 >= fw_bottom - 4.0]

            remaining_left = [l for l in remaining_left if l not in band_left]
            remaining_right = [l for l in remaining_right if l not in band_right]

            if page_dir == TextDirection.RTL:
                ordered.extend(self._order_lines_by_columns(band_right, page_w, page_h, _depth + 1))
                ordered.extend(self._order_lines_by_columns(band_left, page_w, page_h, _depth + 1))
            else:
                ordered.extend(self._order_lines_by_columns(band_left, page_w, page_h, _depth + 1))
                ordered.extend(self._order_lines_by_columns(band_right, page_w, page_h, _depth + 1))

            ordered.append(fw)

        if page_dir == TextDirection.RTL:
            ordered.extend(self._order_lines_by_columns(remaining_right, page_w, page_h, _depth + 1))
            ordered.extend(self._order_lines_by_columns(remaining_left, page_w, page_h, _depth + 1))
        else:
            ordered.extend(self._order_lines_by_columns(remaining_left, page_w, page_h, _depth + 1))
            ordered.extend(self._order_lines_by_columns(remaining_right, page_w, page_h, _depth + 1))

        return ordered

    def _extract_tables(
        self,
        lines: List[OcrPointLine],
        page_num: int,
        start_idx: int,
        page_w: float,
        page_h: float,
        pil_img,
        scale: float,
        assets_dir: Optional[Path] = None,
    ) -> Tuple[List[OcrPointLine], List[Block]]:
        """Identify multi-column aligned grids from OCR lines and construct TableStructure with crop (TBL-001)."""
        if len(lines) < 4:
            return lines, []

        rows_by_y: List[List[OcrPointLine]] = []
        sorted_by_y = sorted(lines, key=lambda l: -l.y0)

        for line in sorted_by_y:
            placed = False
            for r in rows_by_y:
                if abs(r[0].y0 - line.y0) <= 8.0 and abs(r[0].y1 - line.y1) <= 8.0:
                    r.append(line)
                    placed = True
                    break
            if not placed:
                rows_by_y.append([line])

        for r in rows_by_y:
            r.sort(key=lambda l: l.x0)

        multi_col_rows: List[Tuple[int, List[OcrPointLine]]] = []
        for r_idx, r in enumerate(rows_by_y):
            if len(r) >= 2:
                has_gaps = all(r[i + 1].x0 - r[i].x1 >= 8.0 for i in range(len(r) - 1))
                if has_gaps:
                    multi_col_rows.append((r_idx, r))

        if len(multi_col_rows) < 2:
            return lines, []

        table_clusters: List[List[List[OcrPointLine]]] = []
        curr_cluster: List[List[OcrPointLine]] = []
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

            if any(len(row) != len(col_anchors) for row in cluster):
                continue
            if any(abs(line.x0 - col_anchors[column]) > 12.0
                   for row in cluster for column, line in enumerate(row)):
                continue

            # Invariant: Disambiguate 2-column page layout from a table
            if len(col_anchors) == 2:
                avg_len = sum(len(l.text) for r in cluster for l in r) / max(1, sum(len(r) for r in cluster))
                max_w = max((l.x1 - l.x0) for r in cluster for l in r)
                if avg_len > 35 or max_w > 0.30 * page_w:
                    continue

            grid: List[List[TableCell]] = []
            all_cluster_lines: List[OcrPointLine] = []

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

            # Crop table region from scanned page bitmap for retained visual fallback (TBL-001)
            image_asset: Optional[ImageAsset] = None
            try:
                px_x0 = max(0, int(min_x * scale) - 6)
                px_y0 = max(0, int((page_h - max_y) * scale) - 6)
                px_x1 = min(pil_img.width, int(max_x * scale) + 6)
                px_y1 = min(pil_img.height, int((page_h - min_y) * scale) + 6)
                if px_x1 > px_x0 and px_y1 > px_y0:
                    table_crop = pil_img.crop((px_x0, px_y0, px_x1, px_y1))
                    crop_id = str(uuid.uuid4())[:8]
                    # Keep the retained crop inside the job's asset directory (SEC-004),
                    # never the shared system temp directory.
                    crop_dir = assets_dir if assets_dir is not None else Path(tempfile.gettempdir())
                    crop_path = crop_dir / f"table_{page_num}_{crop_id}.png"
                    table_crop.save(crop_path, format="PNG")
                    image_asset = ImageAsset(
                        asset_id=f"asset_tbl_{crop_id}",
                        file_path=str(crop_path),
                        mime_type="image/png",
                        width=table_crop.width,
                        height=table_crop.height,
                        alt_text=f"Original table scan from page {page_num}",
                    )
            except Exception:
                image_asset = None

            table_struct = TableStructure(rows=grid, has_header=True)
            tbl_text = table_struct.to_markdown_table()
            tbl_lang = detect_language(tbl_text)
            tbl_dir = detect_text_direction(tbl_text)

            tbl_block = Block(
                id=f"p{page_num}_tbl{idx}",
                type=BlockType.TABLE,
                text=tbl_text,
                table_structure=table_struct,
                image_asset=image_asset,
                source_page=page_num,
                source_bounding_box=bbox,
                extraction_method=ExtractionMethod.OCR_FAST,
                confidence=min(0.8, min(line.confidence for line in all_cluster_lines)),
                warnings=["Table structure was inferred from aligned text. Compare with the retained source table or original page."],
                language=tbl_lang,
                text_direction=tbl_dir,
            )
            table_blocks.append(tbl_block)
            idx += 1

        remaining_lines = [l for l in lines if id(l) not in consumed_line_ids]
        return remaining_lines, table_blocks

    def _cluster_semantic_blocks(
        self,
        lines: List[OcrPointLine],
        page_num: int,
        start_idx: int,
        engine_warnings: List[str],
        page_h: float = 792.0,
    ) -> List[Block]:
        """Group OCR lines into semantic blocks (headings, paragraphs, lists, footnotes, captions) with warnings."""
        if not lines:
            return []

        sorted_heights = sorted(l.height for l in lines)
        body_height = sorted_heights[len(sorted_heights) // 2]

        blocks: List[Block] = []
        current_lines: List[OcrPointLine] = []
        current_type = BlockType.PARAGRAPH
        current_level: Optional[int] = None
        idx = start_idx

        def flush_block():
            nonlocal idx, current_lines, current_type, current_level
            if not current_lines:
                return

            text_content = " ".join(l.text.strip() for l in current_lines if l.text.strip())
            if not text_content:
                current_lines = []
                return

            avg_confidence = sum(l.confidence for l in current_lines) / len(current_lines)
            blk_lang = detect_language(text_content)
            blk_dir = detect_text_direction(text_content)

            block_warnings: List[str] = list(engine_warnings)
            if avg_confidence < 0.70:
                block_warnings.append(f"Low OCR confidence ({avg_confidence:.2f})")

            replacement_count = text_content.count("\ufffd")
            if replacement_count > 0:
                block_warnings.append(f"Contains {replacement_count} replacement characters")

            bbox = BoundingBox(
                x0=min(l.x0 for l in current_lines),
                y0=min(l.y0 for l in current_lines),
                x1=max(l.x1 for l in current_lines),
                y1=max(l.y1 for l in current_lines),
            )

            blk = Block(
                id=f"p{page_num}_b{idx}",
                type=current_type,
                text=text_content,
                level=current_level,
                language=blk_lang,
                text_direction=blk_dir,
                source_page=page_num,
                source_bounding_box=bbox,
                extraction_method=ExtractionMethod.OCR_FAST,
                confidence=round(avg_confidence, 3),
                warnings=block_warnings,
            )
            blocks.append(blk)
            idx += 1
            current_lines = []
            current_type = BlockType.PARAGRAPH
            current_level = None

        for line in lines:
            txt = line.text.strip()

            # 1. Footnote detection (FN-001, FN-002)
            is_at_bottom = line.y1 <= 0.28 * page_h
            starts_with_fn_marker = bool(
                re.match(r"^(?:\[\d+\]|\d+[\.\)]|\*|¹|²|³|†|‡|\d+\s+)", txt)
            )
            is_smaller = line.height <= 0.90 * body_height
            is_footnote = is_at_bottom and (
                starts_with_fn_marker or (is_smaller and current_type == BlockType.FOOTNOTE)
            )

            # 2. Caption detection
            is_caption = bool(
                re.match(
                    r"^(?:Figure|Fig\.|Table|Exhibit|Illustration|جدول|شكل)\s+(?:\d+|[A-ZIVX]+)(?::|\.|\s-|\s—)",
                    txt,
                    re.IGNORECASE,
                )
            )

            is_list = txt.startswith(("- ", "* ", "• ", "\u2022 ", "\u25e6 ", "o ", "O ")) or (
                len(txt) > 3 and txt[0].isdigit() and txt[1:3] in (". ", ") ")
            )

            is_heading = False
            heading_level = None
            if not is_footnote and not is_caption and not is_list and len(txt) >= 3:
                if line.height >= 1.5 * body_height:
                    is_heading = True
                    heading_level = 1
                elif line.height >= 1.25 * body_height:
                    is_heading = True
                    heading_level = 2

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
            elif is_list:
                flush_block()
                current_type = BlockType.LIST
                current_lines.append(line)
                flush_block()
            else:
                if current_lines:
                    prev = current_lines[-1]
                    gap = prev.y0 - line.y1
                    horiz_overlap = min(prev.x1, line.x1) - max(prev.x0, line.x0)
                    min_w = min(prev.x1 - prev.x0, line.x1 - line.x0)
                    same_col = (horiz_overlap > 0.25 * min_w) or (abs(prev.x0 - line.x0) < 40.0)
                    max_h = max(prev.height, line.height, 10.0)
                    if gap > 1.75 * max_h or not same_col:
                        flush_block()
                current_lines.append(line)

        flush_block()
        return blocks
