"""Recogniser routing by script (DESIGN.md §4, OCR-001).

There is one recognition pipeline, and it is always the best one installed.
``RoutingMode`` survives for the CLI and library API: ``NATIVE_ONLY`` skips
recognition entirely, ``MAXIMUM_ACCURACY`` renders scanned pages at a higher
resolution, and the other modes are equivalent.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict

from .base import DocumentOcrEngine
from .paddle_engine import PaddleRapidOcrEngine


class RoutingMode(str, Enum):
    AUTOMATIC = "Automatic"
    FAST = "Fast"
    MAXIMUM_ACCURACY = "Maximum accuracy"
    NATIVE_ONLY = "Native text only"


SUPPORTED_SCRIPTS = ("en", "ar")


class OcrRouter:
    """Creates one recogniser per script on demand and closes them together."""

    def __init__(self):
        self._engines: Dict[str, DocumentOcrEngine] = {}

    def close(self) -> None:
        for engine in self._engines.values():
            close = getattr(engine, "close", None)
            if callable(close):
                close()
        self._engines.clear()

    def get_engine(self, mode: RoutingMode = RoutingMode.AUTOMATIC, language: str = "en") -> DocumentOcrEngine:
        script = "ar" if language == "ar" else "en"
        if script not in self._engines:
            self._engines[script] = PaddleRapidOcrEngine(language=script)
        return self._engines[script]

    @staticmethod
    def available_accuracy_languages() -> list[str]:
        """Kept for the desktop health check; recognition is no longer split into packs."""
        return []
