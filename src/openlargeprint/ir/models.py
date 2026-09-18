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
    caption: Optional[str] = None

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        if not self.rows:
            return 0
        return max((len(row) for row in self.rows), default=0)

    def to_markdown_table(self) -> str:
        """Render table as a standard GitHub-flavored markdown table."""
        if not self.rows:
            return ""
        lines = []
        if self.caption:
            lines.append(f"**{self.caption}**\n")
        header_row = self.rows[0]
        header_cells = [c.text.replace("\n", " ").strip() for c in header_row]
        lines.append("| " + " | ".join(header_cells) + " |")
        lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")

        for row in self.rows[1:]:
            row_cells = [c.text.replace("\n", " ").strip() for c in row]
            # Pad or truncate if row length differs
            while len(row_cells) < len(header_cells):
                row_cells.append("")
            lines.append("| " + " | ".join(row_cells[: len(header_cells)]) + " |")

        return "\n".join(lines)

    def to_linearized_text(self) -> str:
        """Render table as an accessible, labeled linearized representation (TBL-001)."""
        if not self.rows:
            return ""
        lines = []
        if self.caption:
            lines.append(f"[Table: {self.caption}]")
        else:
            lines.append("[Table]")

        headers = []
        start_row_idx = 0
        if self.has_header and self.rows:
            headers = [c.text.replace("\n", " ").strip() for c in self.rows[0]]
            start_row_idx = 1
        else:
            col_count = self.column_count
            headers = [f"Column {i + 1}" for i in range(col_count)]

        for r_idx, row in enumerate(self.rows[start_row_idx:], start=1):
            lines.append(f"• Row {r_idx}:")
            for c_idx, cell in enumerate(row):
                header_name = headers[c_idx] if c_idx < len(headers) else f"Column {c_idx + 1}"
                val = cell.text.replace("\n", " ").strip()
                lines.append(f"   - {header_name}: {val}")

        return "\n".join(lines)


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

    def slice_by_source_pages_set(self, page_numbers: set[int]) -> DocumentIR:
        """Return a DocumentIR containing only the specified source pages (OUT-010)."""
        if not page_numbers or any(p < 1 for p in page_numbers):
            raise ValueError(f"Invalid page selection: {page_numbers}")
        filtered_pages = [p for p in self.pages if p.page_number in page_numbers]
        filtered_blocks = [b for b in self.blocks if b.source_page in page_numbers]
        ordered = sorted(page_numbers)
        if len(ordered) == 1:
            title_suffix = f" (Page {ordered[0]})"
        else:
            title_suffix = f" (Pages {', '.join(str(p) for p in ordered)})"
        base_title = self.metadata.title or "Document"
        new_metadata = DocumentMetadata(
            title=f"{base_title}{title_suffix}",
            source_file_name=self.metadata.source_file_name,
            page_count=len(filtered_pages) if filtered_pages else len(ordered),
        )
        return DocumentIR(
            schema_version=self.schema_version,
            metadata=new_metadata,
            pages=filtered_pages,
            blocks=filtered_blocks,
        )
