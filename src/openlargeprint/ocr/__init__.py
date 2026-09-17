"""OCR engine package (OCR-001..007)."""

from .base import (
    DocumentOcrEngine,
    EngineCapabilities,
    EnginePageResult,
    OcrDetectedLine,
)
from .paddle_engine import PaddleRapidOcrEngine
from .router import OcrRouter, RoutingMode

__all__ = [
    "DocumentOcrEngine",
    "EngineCapabilities",
    "EnginePageResult",
    "OcrDetectedLine",
    "OcrRouter",
    "PaddleRapidOcrEngine",
    "RoutingMode",
]
