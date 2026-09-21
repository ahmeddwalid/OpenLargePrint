"""Typed JSON-Lines IPC protocol models for the Tauri bridge (DESIGN.md §9, SEC-005, UI-002..005)."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field

from openlargeprint.version import __version__ as ENGINE_VERSION


class CommandType(str, Enum):
    """Supported narrow typed commands from desktop shell (SEC-005)."""
    HEALTH = "health"
    INSPECT = "inspect"
    CONVERT = "convert"
    EXPORT = "export"
    CANCEL = "cancel"
    GET_REVIEW_DATA = "get_review_data"
    RETRY_PAGE = "retry_page"


class EventType(str, Enum):
    """Events emitted from Python sidecar to desktop shell."""
    HEALTH = "health"
    PROGRESS = "progress"
    CHECKPOINT = "checkpoint"
    SUCCESS = "success"
    ERROR = "error"
    REVIEW_DATA = "review_data"
    INSPECT_RESULT = "inspect_result"
    CANCELLED = "cancelled"


# --- Inbound Commands ---

class HealthCheckCommand(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: Literal[CommandType.HEALTH] = CommandType.HEALTH


class InspectCommand(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: Literal[CommandType.INSPECT] = CommandType.INSPECT
    file_path: str


class ConvertCommand(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: Literal[CommandType.CONVERT] = CommandType.CONVERT
    file_path: str
    output_path: str
    preset: str = "Large"
    paper_size: str = "A4"
    export_format: str = "docx"
    routing_mode: str = "automatic"
    page_range: Optional[Any] = None
    include_page_markers: bool = True
    monochrome: bool = False
    custom_body_pt: Optional[float] = None
    custom_line_spacing: Optional[float] = None


class ExportCommand(BaseModel):
    """Re-render an already-built DocumentIR without re-extraction or OCR (OUT-002, OUT-010)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: Literal[CommandType.EXPORT] = CommandType.EXPORT
    job_id: str
    output_path: str
    export_format: str = "pdf"
    preset: str = "Large"
    paper_size: str = "A4"
    page_range: Optional[Any] = None
    include_page_markers: bool = True
    monochrome: bool = False
    custom_body_pt: Optional[float] = None
    custom_line_spacing: Optional[float] = None


class CancelCommand(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: Literal[CommandType.CANCEL] = CommandType.CANCEL
    job_id: str


class GetReviewDataCommand(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: Literal[CommandType.GET_REVIEW_DATA] = CommandType.GET_REVIEW_DATA
    job_id: str


class RetryPageCommand(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    command: Literal[CommandType.RETRY_PAGE] = CommandType.RETRY_PAGE
    job_id: str
    page_number: int
    routing_mode: str = "automatic"


# --- Outbound Events ---

class HealthCheckEvent(BaseModel):
    type: Literal[EventType.HEALTH] = EventType.HEALTH
    status: str = "ready"
    engine_version: str = ENGINE_VERSION
    ocr_available: bool = True


class ProgressEvent(BaseModel):
    """Real-time progress notification per page (UI-002)."""
    type: Literal[EventType.PROGRESS] = EventType.PROGRESS
    job_id: str
    stage: str
    current_page: int
    total_pages: int
    percent: float
    message: str  # e.g. "Recognizing scanned text — page 85 of 512" (UI-002)


class CheckpointEvent(BaseModel):
    """Page checkpoint notification ensuring long documents are saved progressively (UI-003)."""
    type: Literal[EventType.CHECKPOINT] = EventType.CHECKPOINT
    job_id: str
    page_number: int
    classification: str
    flagged_for_review: bool
    warning: Optional[str] = None


class FlaggedPageReview(BaseModel):
    """Details for a flagged page displayed on the side-by-side review screen (UI-004)."""
    page_number: int
    reason: str  # Plain-language reason, e.g. "Scanned text required fallback" (UI-005)
    original_crop_path: Optional[str] = None
    converted_text: str
    confidence: float
    can_retry: bool = True


class ReviewDataEvent(BaseModel):
    """Payload for side-by-side review interface (UI-004, UI-005)."""
    type: Literal[EventType.REVIEW_DATA] = EventType.REVIEW_DATA
    job_id: str
    total_flagged: int
    flagged_pages: List[FlaggedPageReview]
    summary_message: str  # "3 pages may need review" (UI-005)


class InspectResultEvent(BaseModel):
    """Response to inspect command."""
    type: Literal[EventType.INSPECT_RESULT] = EventType.INSPECT_RESULT
    file_name: str
    detected_format: str
    page_count: int
    title: Optional[str] = None
    classification_summary: dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class SuccessEvent(BaseModel):
    """Conversion completed successfully."""
    type: Literal[EventType.SUCCESS] = EventType.SUCCESS
    job_id: str
    output_path: str
    format: str
    page_count: int
    flagged_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    document_ir: Optional[dict[str, Any]] = None
    review_items: List[FlaggedPageReview] = Field(default_factory=list)


class CancelledEvent(BaseModel):
    """Job cancelled on user request (UI-002)."""
    type: Literal[EventType.CANCELLED] = EventType.CANCELLED
    job_id: str
    message: str = "Conversion cancelled by user."


class ErrorEvent(BaseModel):
    """Plain-language failure notification (UI-005)."""
    type: Literal[EventType.ERROR] = EventType.ERROR
    job_id: Optional[str] = None
    message: str  # Plain-language explanation (UI-005)
    code: str
