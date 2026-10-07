"""OCR engine package (OCR-001..007)."""

from .base import (
    CancellationToken,
    DocumentOcrEngine,
    EngineCapabilities,
    EnginePageResult,
    OcrDetectedLine,
    OcrWord,
)
from .paddle_engine import PaddleRapidOcrEngine
from .router import OcrRouter, RoutingMode

__all__ = [
    "CancellationToken",
    "DocumentOcrEngine",
    "EngineCapabilities",
    "EnginePageResult",
    "OcrDetectedLine",
    "OcrRouter",
    "OcrWord",
    "PaddleRapidOcrEngine",
    "RoutingMode",
]
