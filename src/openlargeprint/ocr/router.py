"""OCR engine router supporting Automatic, Fast, and Maximum accuracy modes (DESIGN.md §4)."""

from __future__ import annotations

from enum import Enum
from typing import Optional
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
        """Return the OCR engine corresponding to the selected routing mode (default: Automatic)."""
        if self._default_engine is None:
            self._default_engine = PaddleRapidOcrEngine(use_gpu=False)

        if mode == RoutingMode.MAXIMUM_ACCURACY:
            from .vlm_engine import PaddleOcrVlEngine
            return PaddleOcrVlEngine(fallback=self._default_engine)
        elif mode in (RoutingMode.AUTOMATIC, RoutingMode.FAST):
            return self._default_engine
        return self.get_engine(RoutingMode.MAXIMUM_ACCURACY)
