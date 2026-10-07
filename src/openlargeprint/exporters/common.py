"""Presentation rules shared by the PDF, Word and Reader outputs (OUT-001..005).

Keeping these in one place means a book looks the same whichever format the
reader picks: the same picture sizes, the same labels, the same notes.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from openlargeprint.ir.models import Block, BlockType, DocumentIR, PageMetadata

BLANK_TOKEN = "______"
PRINT_REMINDER = "To keep the text this size, print at 100% (actual size), not “fit to page”."
SOURCE_BODY_PT = 10.5  # typical body size of a printed textbook page
PICTURE_DPI = 150.0


def page_label(page_number: int, meta: Optional[PageMetadata]) -> str:
    """"Original page 41 (printed 39)" for the marker between source pages."""
    printed = (meta.details.get("printed_page") if meta else None) or ""
    printed = str(printed).strip()
    if printed and printed != str(page_number) and len(printed) <= 8:
        return f"Original page {page_number} (printed {printed})"
    return f"Original page {page_number}"


def pages_by_number(doc: DocumentIR) -> Dict[int, PageMetadata]:
    return {p.page_number: p for p in doc.pages}


def picture_size(block: Block, frame_width: float, frame_height: float, body_pt: float,
                 retained: bool = False) -> Tuple[float, float]:
    """Display size in points: enlarged like the text, never distorted (IMG-003)."""
    asset = block.image_asset
    assert asset is not None
    aspect = asset.height / max(1.0, asset.width)
    if retained:
        width = frame_width
    else:
        source_width = block.source_bounding_box.width if block.source_bounding_box else asset.width * 72.0 / PICTURE_DPI
        enlarge = max(1.0, body_pt / SOURCE_BODY_PT)
        width = source_width * enlarge
        # Do not stretch a small picture beyond twice its own pixels.
        width = min(width, asset.width * 72.0 / PICTURE_DPI * 2.2)
        width = max(width, min(frame_width * 0.35, source_width))
        width = min(width, frame_width)
    height = width * aspect
    max_height = frame_height * 0.86
    if height > max_height:
        height = max_height
        width = height / aspect
    return width, height


def is_retained_page(block: Block) -> bool:
    return bool(block.image_asset and block.image_asset.asset_id.endswith("_retained"))


def reader_note(block: Block) -> Optional[str]:
    """One short, plain note for a flagged block (UI-005, OCR-005)."""
    if is_retained_page(block):
        return block.warnings[0] if block.warnings else None
    if not block.warnings:
        return None
    first = block.warnings[0]
    if first.startswith("Some words here were hard to read"):
        if block.image_asset is not None and block.type not in (BlockType.IMAGE, BlockType.TABLE):
            return "Some words were hard to read, so the original lines are shown below."
        return f"Check against original page {block.source_page}: some words were hard to read."
    return first


def has_original_crop(block: Block) -> bool:
    return block.image_asset is not None and block.type not in (BlockType.IMAGE, BlockType.TABLE)


def caption_label(block: Block) -> Optional[str]:
    if block.role == "figure_text":
        return "In the picture: "
    if block.role == "formula_text":
        return "Formula: "
    return None


def split_marker(block: Block) -> Tuple[Optional[str], str]:
    """Separate a list marker from the rest of the item text."""
    text = block.text or ""
    marker = block.list_marker
    if marker and text.startswith(marker):
        return marker, text[len(marker):].lstrip()
    return None, text


def styled_segments(text: str, styles, offset: int = 0) -> List[Tuple[str, Tuple[str, ...]]]:
    """Split ``text`` into runs tagged with ("b", "i", "u") from the block's emphasis.

    ``offset`` is where ``text`` starts inside the block text (after a list marker).
    """
    if not styles:
        return [(text, ())]
    cuts = {0, len(text)}
    for s in styles:
        for edge in (s.start - offset, s.end - offset):
            if 0 < edge < len(text):
                cuts.add(edge)
    points = sorted(cuts)
    runs: List[Tuple[str, Tuple[str, ...]]] = []
    for a, b in zip(points, points[1:]):
        tags = []
        for flag, tag in (("bold", "b"), ("italic", "i"), ("underline", "u")):
            if any(getattr(s, flag) and s.start - offset <= a and b <= s.end - offset for s in styles):
                tags.append(tag)
        runs.append((text[a:b], tuple(tags)))
    return runs


def table_as_entries(table) -> List[Tuple[str, List[Tuple[Optional[str], str]]]]:
    """A too-wide table read row by row: the first cell leads, the others follow with their headings."""
    rows = table.rows
    if not rows:
        return []
    header = [c.text.strip() for c in rows[0]] if table.has_header else None
    body = rows[1:] if header else rows
    entries = []
    for row in body:
        cells = [c.text.strip() for c in row]
        if not any(cells):
            continue
        lead = cells[0] if cells else ""
        rest = []
        for index, value in enumerate(cells[1:], start=1):
            if value:
                label = header[index] if header and index < len(header) and header[index] else None
                rest.append((label, value))
        entries.append((lead, rest))
    return entries


def source_page_range(blocks: List[Block]) -> Tuple[int, int]:
    pages = [b.source_page for b in blocks]
    return (min(pages), max(pages)) if pages else (0, 0)
