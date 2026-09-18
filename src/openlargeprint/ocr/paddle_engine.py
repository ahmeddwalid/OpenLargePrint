"""PaddleOCR CPU-friendly engine adapter via RapidOCR (OCR-001, OCR-002, OCR-006)."""

from __future__ import annotations

import time
from typing import Optional, Tuple
from PIL import Image
from openlargeprint.security.isolation import log_safe_info
from .base import DocumentOcrEngine, EngineCapabilities, EnginePageResult, OcrDetectedLine


class PaddleRapidOcrEngine:
    """CPU-friendly PaddleOCR engine adapter running on-device via ONNX Runtime."""

    def __init__(self, use_gpu: bool = True):
        self._engine = None
        self.use_gpu = use_gpu

    def _get_engine(self):
        """Lazy-initialize OCR engine on first use with optimal GPU/CPU acceleration."""
        if self._engine is None:
            import os
            import onnxruntime
            from rapidocr_onnxruntime import RapidOCR

            available_providers = onnxruntime.get_available_providers()
            has_cuda = "CUDAExecutionProvider" in available_providers
            has_dml = "DmlExecutionProvider" in available_providers
            has_trt = "TensorrtExecutionProvider" in available_providers

            gpu_available = self.use_gpu and (has_cuda or has_dml or has_trt)
            cpu_threads = min(8, max(1, (os.cpu_count() or 4)))

            hw_desc = "NVIDIA CUDA GPU" if has_cuda else ("DirectML GPU" if has_dml else f"Multi-core CPU ({cpu_threads} threads)")
            log_safe_info(f"Initializing PaddleOCR high-performance engine via {hw_desc}")

            # Configure optimal execution parameters for high-tier hardware
            cfg = {
                "use_cuda": gpu_available and has_cuda,
                "use_dml": gpu_available and has_dml,
                "intra_op_num_threads": cpu_threads,
                "inter_op_num_threads": min(4, cpu_threads),
            }

            self._engine = RapidOCR(
                Det=cfg,
                Cls=cfg,
                Rec=cfg,
            )
        return self._engine

    def capabilities(self) -> EngineCapabilities:
        import onnxruntime
        providers = onnxruntime.get_available_providers()
        is_gpu = any(p in providers for p in ("CUDAExecutionProvider", "DmlExecutionProvider", "TensorrtExecutionProvider"))

        return EngineCapabilities(
            engine_name="PaddleOCR-PP-OCRv4/v6 (RapidOCR)",
            supports_layout=True,
            supports_confidence=True,
            supported_languages=["en", "ar", "fr", "de", "es", "zh"],
            is_gpu_accelerated=is_gpu,
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
