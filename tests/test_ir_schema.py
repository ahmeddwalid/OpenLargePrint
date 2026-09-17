"""Schema and validation tests for DocumentIR (DOC-003)."""

import pytest
from pydantic import ValidationError as PydanticValidationError
from openlargeprint.ir import (
    Block,
    BlockType,
    BoundingBox,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    ImageAsset,
    PageClassification,
    PageMetadata,
    TableStructure,
    TableCell,
    TextDirection,
    document_from_json,
    document_to_json,
    validate_document_ir,
    ValidationError,
)


def test_document_ir_roundtrip():
    """Verify that DocumentIR serializes to and from JSON without information loss."""
    metadata = DocumentMetadata(
        title="Test Law Book Chapter",
        source_file_name="sample_law.pdf",
        page_count=2,
    )
    pages = [
        PageMetadata(
            page_number=1,
            width=595.0,
            height=842.0,
            rotation=0,
            classification=PageClassification.NATIVE,
        ),
        PageMetadata(
            page_number=2,
            width=595.0,
            height=842.0,
            rotation=0,
            classification=PageClassification.NATIVE,
        ),
    ]
    blocks = [
        Block(
            id="blk-001",
            type=BlockType.PAGE_MARKER,
            source_page=1,
            page_marker=1,
            extraction_method=ExtractionMethod.NATIVE,
        ),
        Block(
            id="blk-002",
            type=BlockType.HEADING,
            text="Chapter 1: The Principle of Legality",
            level=1,
            source_page=1,
            source_bounding_box=BoundingBox(x0=50.0, y0=750.0, x1=545.0, y1=780.0),
            extraction_method=ExtractionMethod.NATIVE,
            confidence=1.0,
        ),
        Block(
            id="blk-003",
            type=BlockType.PARAGRAPH,
            text="The doctrine forms the foundation of modern jurisprudence.",
            source_page=1,
            source_bounding_box=BoundingBox(x0=50.0, y0=700.0, x1=280.0, y1=740.0),
            extraction_method=ExtractionMethod.NATIVE,
            confidence=1.0,
        ),
        Block(
            id="blk-004",
            type=BlockType.IMAGE,
            source_page=2,
            source_bounding_box=BoundingBox(x0=100.0, y0=400.0, x1=500.0, y1=700.0),
            image_asset=ImageAsset(
                asset_id="img-001",
                file_path="/tmp/img.png",
                mime_type="image/png",
                width=800,
                height=600,
                alt_text="Figure 1.1 Diagram",
            ),
            extraction_method=ExtractionMethod.NATIVE,
        ),
    ]

    doc = DocumentIR(
        schema_version="1.0.0",
        metadata=metadata,
        pages=pages,
        blocks=blocks,
    )

    # Validate
    warnings = validate_document_ir(doc)
    assert len(warnings) == 0

    # JSON Roundtrip
    json_str = document_to_json(doc)
    restored = document_from_json(json_str)

    assert restored.schema_version == "1.0.0"
    assert restored.metadata.title == "Test Law Book Chapter"
    assert len(restored.pages) == 2
    assert len(restored.blocks) == 4
    assert restored.blocks[1].type == BlockType.HEADING
    assert restored.blocks[1].text == "Chapter 1: The Principle of Legality"
    assert restored.blocks[3].image_asset.width == 800


def test_schema_rejects_extra_fields():
    """Verify that extra unknown fields are rejected to prevent schema drift."""
    valid_data = {
        "schema_version": "1.0.0",
        "metadata": {"title": "Doc", "page_count": 1},
        "pages": [],
        "blocks": [],
        "unexpected_extra_field": "disallowed",
    }
    with pytest.raises(PydanticValidationError):
        DocumentIR.model_validate(valid_data)


def test_validation_detects_invalid_source_page():
    """Verify that 0 or negative source pages are rejected (PDF-006)."""
    doc = DocumentIR(
        metadata=DocumentMetadata(page_count=1),
        pages=[PageMetadata(page_number=1, width=500, height=500, classification=PageClassification.NATIVE)],
        blocks=[
            Block(
                id="blk-bad",
                type=BlockType.PARAGRAPH,
                text="Text",
                source_page=0,  # Invalid: pages are 1-indexed
            )
        ],
    )
    with pytest.raises(ValidationError, match="invalid source_page"):
        validate_document_ir(doc)


def test_image_block_requires_image_asset():
    """Verify that an IMAGE block must carry an image_asset."""
    doc = DocumentIR(
        metadata=DocumentMetadata(page_count=1),
        pages=[PageMetadata(page_number=1, width=500, height=500, classification=PageClassification.NATIVE)],
        blocks=[
            Block(
                id="blk-img-bad",
                type=BlockType.IMAGE,
                source_page=1,
                image_asset=None,
            )
        ],
    )
    with pytest.raises(ValidationError, match="image_asset is None"):
        validate_document_ir(doc)


def test_dict_serialization_and_table_validation():
    """Verify dictionary conversion and table block validation."""
    from openlargeprint.ir.serialization import document_to_dict, document_from_dict
    
    doc = DocumentIR(
        metadata=DocumentMetadata(page_count=1),
        pages=[PageMetadata(page_number=1, width=500, height=500, classification=PageClassification.NATIVE)],
        blocks=[
            Block(
                id="blk-tbl-bad",
                type=BlockType.TABLE,
                source_page=1,
                table_structure=None,
            )
        ],
    )
    # Validation must catch missing table_structure
    with pytest.raises(ValidationError, match="table_structure is None"):
        validate_document_ir(doc)

    # Valid doc dict roundtrip
    valid_doc = DocumentIR(
        metadata=DocumentMetadata(page_count=1),
        pages=[PageMetadata(page_number=1, width=500, height=500, classification=PageClassification.NATIVE)],
        blocks=[
            Block(
                id="blk-p",
                type=BlockType.PARAGRAPH,
                text="Some text",
                source_page=1,
            )
        ],
    )
    d = document_to_dict(valid_doc)
    assert isinstance(d, dict)
    restored = document_from_dict(d)
    assert restored.metadata.page_count == 1
    assert restored.blocks[0].text == "Some text"
