"""Scanned PDF layout and OCR text extraction (PDF-003, PDF-006, OCR-004, OCR-005)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import pypdfium2 as pdfium

from openlargeprint.ir.models import (
    Block,
    BlockType,
    BoundingBox,
    ExtractionMethod,
    TextDirection,
)
from openlargeprint.ocr.base import DocumentOcrEngine, OcrDetectedLine
from openlargeprint.security.isolation import log_safe_info


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

    def __init__(self, ocr_engine: DocumentOcrEngine, dpi: float = 200.0):
        self.ocr_engine = ocr_engine
        self.dpi = dpi

    def extract_page(
        self,
        page: pdfium.PdfPage,
        page_num: int,
        start_block_idx: int,
    ) -> List[Block]:
        """Render page, perform OCR recognition, reconstruct columns, and form semantic blocks."""
        page_w_pt, page_h_pt = page.get_size()
        scale = self.dpi / 72.0

        # 1. Render page bitmap at OCR resolution (PDF-003)
        bitmap = page.render(scale=scale)
        pil_img = bitmap.to_pil()

        # 2. Run OCR recognition (OCR-001, OCR-002, OCR-006)
        ocr_res = self.ocr_engine.analyze_page(pil_img, page_num=page_num)
        log_safe_info(
            f"Page {page_num} OCR recognized {len(ocr_res.lines)} lines in {ocr_res.elapse_seconds:.2f}s"
        )

        if not ocr_res.lines:
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

        # 4. Reconstruct multi-column reading order (PDF-003)
        ordered_lines = self._order_lines_by_columns(point_lines, page_w_pt, page_h_pt)

        # 5. Form semantic blocks with confidence and warnings (OCR-004, OCR-005)
        blocks = self._cluster_semantic_blocks(
            ordered_lines, page_num, start_block_idx, ocr_res.warnings
        )
        return blocks

    def _order_lines_by_columns(
        self, lines: List[OcrPointLine], page_w: float, page_h: float
    ) -> List[OcrPointLine]:
        """Reconstruct proper reading order for single- or multi-column scanned pages."""
        if len(lines) <= 2:
            return sorted(lines, key=lambda l: -l.y1)

        mid_x = page_w / 2.0
        left_col: List[OcrPointLine] = []
        right_col: List[OcrPointLine] = []
        full_width: List[OcrPointLine] = []

        for line in lines:
            if line.x0 < mid_x * 0.85 and line.x1 > mid_x * 1.15:
                # Spans across page center
                full_width.append(line)
            elif line.x1 <= mid_x + 20:
                left_col.append(line)
            elif line.x0 >= mid_x - 20:
                right_col.append(line)
            else:
                full_width.append(line)

        is_two_column = len(left_col) >= 2 and len(right_col) >= 2
        if not is_two_column:
            # Single-column: sort top-to-bottom
            return sorted(lines, key=lambda l: -l.y1)

        # Multi-column layout:
        col_top = max(max(l.y1 for l in left_col), max(l.y1 for l in right_col))
        col_bottom = min(min(l.y0 for l in left_col), min(l.y0 for l in right_col))

        top_headers = [l for l in full_width if l.y0 >= col_top - 10]
        bottom_footers = [l for l in full_width if l.y1 <= col_bottom + 10]
        middle_full = [l for l in full_width if l not in top_headers and l not in bottom_footers]

        ordered: List[OcrPointLine] = []
        ordered.extend(sorted(top_headers, key=lambda l: -l.y1))
        ordered.extend(sorted(left_col, key=lambda l: -l.y1))
        ordered.extend(sorted(right_col, key=lambda l: -l.y1))
        ordered.extend(sorted(middle_full, key=lambda l: -l.y1))
        ordered.extend(sorted(bottom_footers, key=lambda l: -l.y1))
        return ordered

    def _cluster_semantic_blocks(
        self,
        lines: List[OcrPointLine],
        page_num: int,
        start_idx: int,
        engine_warnings: List[str],
    ) -> List[Block]:
        """Group OCR lines into semantic blocks (headings, paragraphs, lists) with warnings."""
        if not lines:
            return []

        # Find median line height to calibrate heading and paragraph thresholds
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

            text_content = " ".join(l.text for l in current_lines)
            avg_confidence = sum(l.confidence for l in current_lines) / len(current_lines)

            # Check OCR-005 quality gates
            block_warnings: List[str] = list(engine_warnings)
            if avg_confidence < 0.70:
                block_warnings.append(f"Low OCR confidence ({avg_confidence:.2f})")

            # Check for gibberish/replacement characters (OCR-005)
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
            # Check for heading
            is_heading = False
            heading_level = None

            if line.height >= 1.5 * body_height:
                is_heading = True
                heading_level = 1
            elif line.height >= 1.25 * body_height:
                is_heading = True
                heading_level = 2

            # Check for list item
            is_list = line.text.startswith(("- ", "* ", "• ", "\u2022 ", "\u25e6 ")) or (
                len(line.text) > 3 and line.text[0].isdigit() and line.text[1:3] in (". ", ") ")
            )

            if is_heading:
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
                    same_col = abs(prev.x0 - line.x0) < 60
                    if gap > 2.0 * prev.height or not same_col:
                        flush_block()
                current_lines.append(line)

        flush_block()
        return blocks
