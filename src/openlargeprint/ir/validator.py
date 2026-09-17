"""Validation and integrity checks for DocumentIR (DOC-003, DESIGN.md §3)."""

from __future__ import annotations

from typing import List
from .models import DocumentIR, BlockType, PageClassification


class ValidationError(Exception):
    """Raised when DocumentIR fails structural integrity checks."""
    pass


def validate_document_ir(doc: DocumentIR) -> List[str]:
    """Validate DocumentIR against project integrity requirements.
    
    Returns a list of warning strings if non-fatal anomalies are found,
    or raises ValidationError if invariants are violated.
    """
    warnings: List[str] = []

    if doc.metadata.page_count < 0:
        raise ValidationError(f"Invalid page count: {doc.metadata.page_count}")

    if len(doc.pages) != doc.metadata.page_count:
        warnings.append(
            f"Page count mismatch: metadata reports {doc.metadata.page_count}, but {len(doc.pages)} pages present"
        )

    # Check for empty document when pages are classified as native
    has_native_pages = any(p.classification == PageClassification.NATIVE for p in doc.pages)
    if has_native_pages and len(doc.blocks) == 0:
        warnings.append("Document has native pages but no extracted blocks")

    # Check block provenance invariants (PDF-006)
    for i, block in enumerate(doc.blocks):
        if block.source_page < 1:
            raise ValidationError(f"Block {block.id} (index {i}) has invalid source_page: {block.source_page}")

        if block.type == BlockType.IMAGE and block.image_asset is None:
            raise ValidationError(f"Block {block.id} is IMAGE type but image_asset is None")

        if block.type == BlockType.TABLE and block.table_structure is None:
            raise ValidationError(f"Block {block.id} is TABLE type but table_structure is None")

        if block.type == BlockType.PAGE_MARKER and block.page_marker is None:
            raise ValidationError(f"Block {block.id} is PAGE_MARKER type but page_marker is None")

    return warnings
