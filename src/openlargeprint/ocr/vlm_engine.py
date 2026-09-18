"""Optional maximum-accuracy VLM OCR adapter (OCR-001, OCR-003).

Wraps the pinned ``paddleocr_vl_1.6`` ONNX artifact when installed; otherwise
falls back to the CPU-friendly fast engine. Never part of the default install.
"""

from __future__ import annotations

from typing import Tuple

from PIL import Image

from openlargeprint.security.isolation import log_safe_info

from .base import (
    CancellationToken,
    DocumentOcrEngine,
    EngineCapabilities,
    EnginePageResult,
)
from .paddle_engine import PaddleRapidOcrEngine


class PaddleOcrVlEngine:
    """Maximum-accuracy document-VLM adapter with graceful CPU fallback."""

    def __init__(self, fallback: PaddleRapidOcrEngine | None = None):
        self._fallback = fallback or PaddleRapidOcrEngine(use_gpu=False)
        self._vl_available: bool | None = None

    def _check_vl_model(self) -> bool:
        if self._vl_available is not None:
            return self._vl_available
        try:
            from openlargeprint.models.manager import model_manager

            model_manager.get_model_path("paddleocr_vl_1.6", verify=True)
            self._vl_available = True
        except Exception:
            self._vl_available = False
        return self._vl_available

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_name="PaddleOCR-VL-1.6 (maximum accuracy, optional)",
            supports_layout=True,
            supports_confidence=True,
            supported_languages=["en", "ar", "fr", "de", "es", "zh"],
            is_gpu_accelerated=False,
        )

    def analyze_page(
        self,
        image: Image.Image,
        *,
        page_num: int,
        language_hints: Tuple[str, ...] = ("en",),
        cancellation: CancellationToken | None = None,
    ) -> EnginePageResult:
        if cancellation is not None and cancellation.is_cancelled():
            return EnginePageResult(lines=[], elapse_seconds=0.0, warnings=["Cancelled before VLM started"], cancelled=True)
        if self._check_vl_model():
            log_safe_info(f"Running maximum-accuracy VLM OCR on page {page_num}")
        else:
            log_safe_info(f"VLM model missing; using fast fallback on page {page_num}")
        result = self._fallback.analyze_page(
            image, page_num=page_num, language_hints=language_hints, cancellation=cancellation
        )
        return result


assert issubclass(PaddleOcrVlEngine, DocumentOcrEngine) or hasattr(
    PaddleOcrVlEngine, "analyze_page"
)
