"""OCR engine router supporting Automatic, Fast, and Maximum accuracy modes (DESIGN.md §4)."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from openlargeprint.security.isolation import log_safe_info
from .base import DocumentOcrEngine
from .paddle_engine import PaddleRapidOcrEngine


class RoutingMode(str, Enum):
    """Routing modes exposed behind Advanced options (UI-001, DESIGN.md §4)."""
    AUTOMATIC = "Automatic"
    FAST = "Fast"
    MAXIMUM_ACCURACY = "Maximum accuracy"


class OcrRouter:
    """Routes pages to the appropriate OCR engine based on user preference and availability."""

    def __init__(self):
        self._default_engine: Optional[DocumentOcrEngine] = None

    def get_engine(self, mode: RoutingMode = RoutingMode.AUTOMATIC) -> DocumentOcrEngine:
        """Return the OCR engine corresponding to the selected routing mode."""
        if mode in (RoutingMode.AUTOMATIC, RoutingMode.FAST):
            if self._default_engine is None:
                self._default_engine = PaddleRapidOcrEngine()
            return self._default_engine
        elif mode == RoutingMode.MAXIMUM_ACCURACY:
            # For Maximum accuracy, if heavy model pack is not separately downloaded,
            # fall back gracefully to the default CPU engine
            log_safe_info("Maximum accuracy requested; using default CPU engine (optional pack not installed)")
            if self._default_engine is None:
                self._default_engine = PaddleRapidOcrEngine()
            return self._default_engine
        return self.get_engine(RoutingMode.AUTOMATIC)
