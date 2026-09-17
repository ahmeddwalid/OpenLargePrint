"""PaddleOCR CPU-friendly engine adapter via RapidOCR (OCR-001, OCR-002, OCR-006)."""

from __future__ import annotations

import time
from typing import Optional, Tuple
from PIL import Image
from openlargeprint.security.isolation import log_safe_info
from .base import DocumentOcrEngine, EngineCapabilities, EnginePageResult, OcrDetectedLine


class PaddleRapidOcrEngine:
    """CPU-friendly PaddleOCR engine adapter running on-device via ONNX Runtime."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        """Lazy-initialize OCR engine on first use to avoid overhead during native extraction."""
        if self._engine is None:
            log_safe_info("Initializing PaddleOCR (ONNX CPU runtime)")
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        return self._engine

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_name="PaddleOCR-PP-OCRv4/v6 (RapidOCR)",
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
    ) -> EnginePageResult:
        engine = self._get_engine()
        start_time = time.perf_counter()

        log_safe_info(f"Running OCR on rendered page {page_num} ({image.width}x{image.height}px)")
        raw_result, elapse = engine(image)
        total_time = time.perf_counter() - start_time

        lines: list[OcrDetectedLine] = []
        warnings: list[str] = []

        if raw_result:
            for item in raw_result:
                try:
                    box_points, text, confidence = item
                    # box_points is [[x0,y0], [x1,y0], [x1,y1], [x0,y1]]
                    polygon = [(float(p[0]), float(p[1])) for p in box_points]
                    score = float(confidence)
                    clean_text = str(text).strip()
                    if clean_text:
                        lines.append(
                            OcrDetectedLine(
                                text=clean_text,
                                polygon=polygon,
                                confidence=score,
                            )
                        )
                        if score < 0.60:
                            warnings.append(f"Low confidence OCR segment ({score:.2f}) on page {page_num}")
                except Exception:
                    continue

        return EnginePageResult(
            lines=lines,
            elapse_seconds=total_time,
            warnings=warnings,
        )
