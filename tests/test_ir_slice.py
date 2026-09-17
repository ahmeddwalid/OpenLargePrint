"""Tests for DocumentIR selective page slicing (OUT-010)."""

import pytest
from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    PageClassification,
    PageMetadata,
)


def create_three_page_ir() -> DocumentIR:
    metadata = DocumentMetadata(title="Principles of Statutory Interpretation", page_count=3)
    pages = [
        PageMetadata(page_number=1, width=500, height=700, classification=PageClassification.NATIVE),
        PageMetadata(page_number=2, width=500, height=700, classification=PageClassification.NATIVE),
        PageMetadata(page_number=3, width=500, height=700, classification=PageClassification.NATIVE),
    ]
    blocks = [
        Block(id="p1_m", type=BlockType.PAGE_MARKER, source_page=1, page_marker=1),
        Block(id="p1_b1", type=BlockType.PARAGRAPH, text="Page 1 text", source_page=1),
        Block(id="p2_m", type=BlockType.PAGE_MARKER, source_page=2, page_marker=2),
        Block(id="p2_b1", type=BlockType.HEADING, text="Chapter 2 Heading", level=1, source_page=2),
        Block(id="p2_b2", type=BlockType.PARAGRAPH, text="Page 2 text", source_page=2),
        Block(id="p3_m", type=BlockType.PAGE_MARKER, source_page=3, page_marker=3),
        Block(id="p3_b1", type=BlockType.PARAGRAPH, text="Page 3 text", source_page=3),
    ]
    return DocumentIR(metadata=metadata, pages=pages, blocks=blocks)


def test_slice_middle_page():
    """Verify slicing just page 2 retains only page 2 blocks and updates metadata (OUT-010)."""
    doc = create_three_page_ir()
    sliced = doc.slice_by_source_pages(2, 2)

    assert sliced.metadata.page_count == 1
    assert "Page 2" in sliced.metadata.title
    assert len(sliced.pages) == 1
    assert sliced.pages[0].page_number == 2

    # Verify only page 2 blocks are included
    assert len(sliced.blocks) == 3
    for b in sliced.blocks:
        assert b.source_page == 2

    assert sliced.blocks[1].text == "Chapter 2 Heading"


def test_slice_page_range():
    """Verify slicing a contiguous range (e.g. pages 2 to 3) works properly (OUT-010)."""
    doc = create_three_page_ir()
    sliced = doc.slice_by_source_pages(2, 3)

    assert sliced.metadata.page_count == 2
    assert "Pages 2–3" in sliced.metadata.title
    assert len(sliced.pages) == 2
    assert len(sliced.blocks) == 5

    source_pages = {b.source_page for b in sliced.blocks}
    assert source_pages == {2, 3}


def test_slice_invalid_ranges():
    """Verify that invalid page ranges raise ValueError."""
    doc = create_three_page_ir()

    with pytest.raises(ValueError, match="Invalid page range"):
        doc.slice_by_source_pages(0, 2)  # Page numbers are 1-indexed

    with pytest.raises(ValueError, match="Invalid page range"):
        doc.slice_by_source_pages(3, 2)  # End before start
