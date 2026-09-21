"""PaddleOCR CPU-friendly engine adapter via RapidOCR (OCR-001, OCR-002, OCR-006)."""

from __future__ import annotations

import time
from typing import Optional, Tuple
from PIL import Image
from openlargeprint.security.isolation import log_safe_info
from .base import CancellationToken, EngineCapabilities, EnginePageResult, OcrDetectedLine

MAX_CPU_THREADS = 8
INTER_OP_THREADS = 1

class PaddleRapidOcrEngine:
    """CPU-friendly PaddleOCR engine adapter running on-device via ONNX Runtime."""

    def __init__(self, use_gpu: bool = False):
        self._engine = None
        self.use_gpu = use_gpu

    def _get_engine(self):
        """Lazy-initialize OCR engine on first use with optimal GPU/CPU acceleration."""
        if self._engine is None:
            import os
            import onnxruntime
            from rapidocr_onnxruntime import RapidOCR
            from pathlib import Path
            import rapidocr_onnxruntime
            from openlargeprint.models import PINNED_MODELS, ModelManager, ModelIntegrityError

            model_root = Path(rapidocr_onnxruntime.__file__).parent / "models"
            model_paths = {}
            for stage, key in (("det", "ch_PP-OCRv4_det"), ("cls", "ch_ppocr_mobile_v2.0_cls"), ("rec", "ch_PP-OCRv4_rec")):
                path = model_root / f"{key}_infer.onnx"
                artifact = PINNED_MODELS.models[key]
                if ModelManager.compute_sha256(path) != artifact.sha256:
                    raise ModelIntegrityError("The bundled recognition model failed integrity verification. Reinstall the application.")
                model_paths[f"{stage}_model_path"] = str(path)

            available_providers = onnxruntime.get_available_providers()
            has_cuda = "CUDAExecutionProvider" in available_providers
            has_dml = "DmlExecutionProvider" in available_providers
            has_trt = "TensorrtExecutionProvider" in available_providers

            gpu_available = self.use_gpu and (has_cuda or has_dml or has_trt)
            cpu_threads = min(MAX_CPU_THREADS, max(1, (os.cpu_count() or 4) - 1))

            hw_desc = "NVIDIA CUDA GPU" if gpu_available and has_cuda else ("DirectML GPU" if gpu_available and has_dml else f"Multi-core CPU ({cpu_threads} threads)")
            log_safe_info(f"Initializing PaddleOCR high-performance engine via {hw_desc}")

            # Configure optimal execution parameters for high-tier hardware
            cfg = {
                "det_use_cuda": gpu_available and has_cuda,
                "cls_use_cuda": gpu_available and has_cuda,
                "rec_use_cuda": gpu_available and has_cuda,
                "det_use_dml": gpu_available and has_dml and not has_cuda,
                "cls_use_dml": gpu_available and has_dml and not has_cuda,
                "rec_use_dml": gpu_available and has_dml and not has_cuda,
                "intra_op_num_threads": cpu_threads,
                "inter_op_num_threads": INTER_OP_THREADS,
            }

            self._engine = RapidOCR(**cfg, **model_paths)
        return self._engine

    def capabilities(self) -> EngineCapabilities:
        import onnxruntime
        providers = onnxruntime.get_available_providers()
        is_gpu = self.use_gpu and any(p in providers for p in ("CUDAExecutionProvider", "DmlExecutionProvider"))

        return EngineCapabilities(
            engine_name="PP-OCRv4 (RapidOCR)",
            supports_layout=False,
            supports_confidence=True,
            supported_languages=["en", "zh"],
            is_gpu_accelerated=is_gpu,
        )

    def analyze_page(
        self,
        image: Image.Image,
        *,
        page_num: int,
        language_hints: Tuple[str, ...] = ("en",),
        cancellation: Optional[CancellationToken] = None,
    ) -> EnginePageResult:
        if cancellation is not None and cancellation.is_cancelled():
            return EnginePageResult(lines=[], elapse_seconds=0.0, warnings=["Cancelled before OCR started"], cancelled=True)
        engine = self._get_engine()
        start_time = time.perf_counter()

        log_safe_info(f"Running OCR on rendered page {page_num} ({image.width}x{image.height}px)")
        import numpy as np
        img_np = np.array(image.convert("RGB"))
        raw_result, elapse = engine(img_np)
        total_time = time.perf_counter() - start_time

        lines: list[OcrDetectedLine] = []
        warnings: list[str] = []

        if raw_result:
            for item in raw_result:
                if cancellation is not None and cancellation.is_cancelled():
                    return EnginePageResult(lines=lines, elapse_seconds=time.perf_counter() - start_time, warnings=warnings + ["Cancelled mid-page"], cancelled=True)
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
