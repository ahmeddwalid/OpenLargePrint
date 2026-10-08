"""Page layout regions shared by the native and scanned PDF paths (PDF-001, PDF-003, PDF-006).

Coordinates in this module use *page space*: points relative to the page's
visible box, x growing to the right and y growing downwards. Conversion to the
PDF-style bottom-left ``BoundingBox`` stored in ``DocumentIR`` happens only when
blocks are created, through :func:`to_ir_bbox`.

A detector only decides geometry. It never produces or alters text (OCR-007).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Protocol, Sequence, Tuple

from PIL import Image

from openlargeprint.ir.models import BoundingBox


class RegionKind(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    TEXT = "text"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    ASIDE = "aside"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    FORMULA = "formula"
    CONTENTS = "contents"


# PP-DocLayout label -> region kind. Labels that carry no reading content of
# their own (seals, header/footer artwork) are treated as figures so they are
# never lost; the assembler decides later whether they are decorative.
LABEL_KINDS = {
    "doc_title": RegionKind.TITLE,
    "paragraph_title": RegionKind.HEADING,
    "text": RegionKind.TEXT,
    "abstract": RegionKind.TEXT,
    "vertical_text": RegionKind.TEXT,
    "reference": RegionKind.TEXT,
    "reference_content": RegionKind.TEXT,
    "algorithm": RegionKind.TEXT,
    "content": RegionKind.CONTENTS,
    "table": RegionKind.TABLE,
    "image": RegionKind.FIGURE,
    "chart": RegionKind.FIGURE,
    "seal": RegionKind.FIGURE,
    "header_image": RegionKind.FIGURE,
    "footer_image": RegionKind.FIGURE,
    "figure_title": RegionKind.CAPTION,
    "vision_footnote": RegionKind.CAPTION,
    "table_title": RegionKind.CAPTION,
    "footnote": RegionKind.FOOTNOTE,
    "aside_text": RegionKind.ASIDE,
    "header": RegionKind.HEADER,
    "footer": RegionKind.FOOTER,
    "number": RegionKind.PAGE_NUMBER,
    "display_formula": RegionKind.FORMULA,
    "inline_formula": RegionKind.FORMULA,
    "formula_number": RegionKind.TEXT,
}

TEXT_KINDS = {
    RegionKind.TITLE, RegionKind.HEADING, RegionKind.TEXT, RegionKind.LIST,
    RegionKind.CAPTION, RegionKind.FOOTNOTE, RegionKind.ASIDE, RegionKind.CONTENTS,
}
MARGIN_KINDS = {RegionKind.HEADER, RegionKind.FOOTER, RegionKind.PAGE_NUMBER}


@dataclass
class LayoutRegion:
    kind: RegionKind
    x0: float
    y0: float
    x1: float
    y1: float
    score: float = 1.0
    order: int = 0
    label: str = ""
    decorative: bool = False

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def box(self) -> Tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

    def contains_point(self, x: float, y: float, pad: float = 0.0) -> bool:
        return self.x0 - pad <= x <= self.x1 + pad and self.y0 - pad <= y <= self.y1 + pad


@dataclass
class PageLayout:
    width: float
    height: float
    regions: List[LayoutRegion] = field(default_factory=list)
    source: str = "model"


class LayoutDetector(Protocol):
    """Engine-neutral layout interface (DESIGN.md §4): image in, ordered regions out."""

    name: str

    def detect(self, image: Image.Image, page_width: float, page_height: float) -> PageLayout:
        ...


def overlap_area(a: Sequence[float], b: Sequence[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def box_area(a: Sequence[float]) -> float:
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


def coverage(inner: Sequence[float], outer: Sequence[float]) -> float:
    """Fraction of ``inner`` that lies inside ``outer``."""
    area = box_area(inner)
    return overlap_area(inner, outer) / area if area > 0 else 0.0


def union_box(boxes: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def to_ir_bbox(box: Sequence[float], page_height: float) -> BoundingBox:
    """Page space (y down) -> DocumentIR PDF points (y up) (PDF-006)."""
    return BoundingBox(x0=float(box[0]), y0=float(page_height - box[3]),
                       x1=float(box[2]), y1=float(page_height - box[1]))


def best_region(box: Sequence[float], regions: Sequence[LayoutRegion],
                kinds: Optional[set] = None, minimum: float = 0.5) -> Optional[LayoutRegion]:
    """Region holding the largest share of ``box`` (at least ``minimum``)."""
    best, best_share = None, minimum
    for region in regions:
        if kinds is not None and region.kind not in kinds:
            continue
        share = coverage(box, region.box)
        if share > best_share or (share == best_share and best is not None and region.area < best.area):
            best, best_share = region, share
    return best
