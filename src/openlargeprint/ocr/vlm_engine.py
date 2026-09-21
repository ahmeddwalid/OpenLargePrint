from __future__ import annotations

from typing import Tuple
from PIL import Image

from .base import CancellationToken, EngineCapabilities, EnginePageResult
from .paddle_engine import PaddleRapidOcrEngine


class PaddleOcrVlEngine:
    def __init__(self, fallback: PaddleRapidOcrEngine | None = None):
        self._fallback = fallback or PaddleRapidOcrEngine(use_gpu=False)

    def capabilities(self) -> EngineCapabilities:
        capabilities = self._fallback.capabilities()
        capabilities.engine_name += " (maximum-accuracy fallback)"
        return capabilities

    def analyze_page(
        self,
        image: Image.Image,
        *,
        page_num: int,
        language_hints: Tuple[str, ...] = ("en",),
        cancellation: CancellationToken | None = None,
    ) -> EnginePageResult:
        result = self._fallback.analyze_page(
            image, page_num=page_num, language_hints=language_hints, cancellation=cancellation
        )
        result.warnings.append("Maximum accuracy is not available in this build. This page used standard recognition and needs review.")
        return result
