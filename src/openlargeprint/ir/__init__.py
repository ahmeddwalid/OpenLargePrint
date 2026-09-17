"""DocumentIR package."""

from .models import (
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
from .serialization import (
    document_from_dict,
    document_from_json,
    document_to_dict,
    document_to_json,
)
from .validator import ValidationError, validate_document_ir

__all__ = [
    "Block",
    "BlockType",
    "BoundingBox",
    "DocumentIR",
    "DocumentMetadata",
    "ExtractionMethod",
    "ImageAsset",
    "PageClassification",
    "PageMetadata",
    "TableCell",
    "TableStructure",
    "TextDirection",
    "ValidationError",
    "document_from_dict",
    "document_from_json",
    "document_to_dict",
    "document_to_json",
    "validate_document_ir",
]
