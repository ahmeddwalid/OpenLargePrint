"""Canonical DocumentIR schema (DOC-001..003, OUT-010).

Every importer in OpenLargePrint normalizes into DocumentIR, and every exporter
reads exclusively from DocumentIR.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    """Bounding box coordinates in points or normalized space."""
    x0: float
    y0: float
    x1: float
    y1: float
    coord_system: str = "pdf_points"

    @property
    def width(self) -> float:
        return abs(self.x1 - self.x0)

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


class BlockType(str, Enum):
    """Semantic block types supported across importers and exporters."""
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    QUOTE = "quote"
    FOOTNOTE = "footnote"
    TABLE = "table"
    IMAGE = "image"
    CAPTION = "caption"
    PAGE_MARKER = "page_marker"


class ExtractionMethod(str, Enum):
    """Method used to extract or recognize a block."""
    NATIVE = "native"
    OCR_FAST = "ocr_fast"
    OCR_MAXIMUM = "ocr_maximum"
    OFFICE_IMPORT = "office_import"


class TextDirection(str, Enum):
    """Text direction for writing systems."""
    LTR = "ltr"
    RTL = "rtl"


class ImageAsset(BaseModel):
    """Asset details for an extracted image (IMG-001, IMG-003)."""
    asset_id: str
    file_path: Optional[str] = None
    mime_type: str = "image/png"
    width: int
    height: int
    alt_text: Optional[str] = None


class TableCell(BaseModel):
    """A single cell within a table."""
    text: str = ""
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False


class TableStructure(BaseModel):
    """Structure representation for semantic tables (TBL-001)."""
    rows: list[list[TableCell]] = Field(default_factory=list)
    has_header: bool = False


class Block(BaseModel):
    """A semantic block carrying content, provenance, and classification (DOC-002)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    type: BlockType
    text: Optional[str] = None
    level: Optional[int] = None  # Heading level (1, 2, 3...) when type == HEADING
    language: Optional[str] = "en"
    text_direction: TextDirection = TextDirection.LTR
    source_page: int  # 1-indexed source page (PDF-006)
    source_bounding_box: Optional[BoundingBox] = None  # (PDF-006)
    extraction_method: ExtractionMethod = ExtractionMethod.NATIVE
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    image_asset: Optional[ImageAsset] = None
    table_structure: Optional[TableStructure] = None
    page_marker: Optional[int] = None  # Original page number if type == PAGE_MARKER (OUT-005)


class PageClassification(str, Enum):
    """Classification of an input page before strategy selection (PDF-001)."""
    NATIVE = "native"
    SCANNED = "scanned"
    MIXED = "mixed"
    BROKEN_DIGITAL = "broken_digital"


class PageMetadata(BaseModel):
    """Page-level diagnostic and structural metadata."""
    page_number: int  # 1-indexed
    width: float
    height: float
    rotation: int = 0  # 0, 90, 180, 270 (PDF-007)
    classification: PageClassification
    details: dict[str, Any] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    """Document-level provenance and execution metadata."""
    title: Optional[str] = None
    source_file_name: Optional[str] = None
    page_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DocumentIR(BaseModel):
    """Canonical document intermediate representation (DOC-001..003)."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    metadata: DocumentMetadata
    pages: list[PageMetadata] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)

    def slice_by_source_pages(self, start_page: int, end_page: int) -> DocumentIR:
        """Return a sliced DocumentIR containing only blocks from start_page to end_page (OUT-010)."""
        if start_page < 1 or end_page < start_page:
            raise ValueError(f"Invalid page range: [{start_page}, {end_page}]")

        filtered_pages = [p for p in self.pages if start_page <= p.page_number <= end_page]
        filtered_blocks = [b for b in self.blocks if start_page <= b.source_page <= end_page]

        title_suffix = f" (Pages {start_page}–{end_page})" if start_page != end_page else f" (Page {start_page})"
        base_title = self.metadata.title or "Document"
        new_metadata = DocumentMetadata(
            title=f"{base_title}{title_suffix}",
            source_file_name=self.metadata.source_file_name,
            page_count=len(filtered_pages) if filtered_pages else (end_page - start_page + 1),
        )

        return DocumentIR(
            schema_version=self.schema_version,
            metadata=new_metadata,
            pages=filtered_pages,
            blocks=filtered_blocks,
        )
