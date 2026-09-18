"""OCR engine package (OCR-001..007)."""

from .base import (
    CancellationToken,
    DocumentOcrEngine,
    EngineCapabilities,
    EnginePageResult,
    OcrDetectedLine,
)
from .paddle_engine import PaddleRapidOcrEngine
from .router import OcrRouter, RoutingMode
from .vlm_engine import PaddleOcrVlEngine

__all__ = [
    "CancellationToken",
    "DocumentOcrEngine",
    "EngineCapabilities",
    "EnginePageResult",
    "OcrDetectedLine",
    "OcrRouter",
    "PaddleOcrVlEngine",
    "PaddleRapidOcrEngine",
    "RoutingMode",
]
