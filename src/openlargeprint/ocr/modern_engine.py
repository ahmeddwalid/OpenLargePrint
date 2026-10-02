"""Optional, local-only RapidOCR 3.9.2 CPU adapter (OCR-001..004, SEC-006/009).

Code: RapidAI/RapidOCR Apache-2.0, pinned release commit
095232a4c94f7f0e6600ba5bba1177010ad696d4. Weight licenses are
recorded separately in the artifact manifest.
"""
from __future__ import annotations

import math
import os
import time
from pathlib import Path

from PIL import Image

from .base import CancellationToken, EngineCapabilities, EnginePageResult, OcrDetectedLine
from .worker import OcrWorker


class ModernRapidOcrEngine:
    def __init__(self, rec_model_path: str, language: str = "en"):
        if language not in ("en", "ar"):
            raise ValueError("This recognition pack does not support that language.")
        self.language = language
        self.rec_model_path = rec_model_path
        self._engine = None
        self._worker = OcrWorker(use_gpu=False, rec_model_path=rec_model_path,
                                 language=language, backend="modern")

    def close(self) -> None:
        self._worker.close()

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_name="PP-OCRv6 medium (RapidOCR)",
            supports_layout=False, supports_confidence=True,
            supported_languages=["en", "zh"],
            is_gpu_accelerated=False,
            recognition_profile="optional_accuracy",
        )

    def _get_engine(self):
        if self.language == "ar":
            raise RuntimeError("Arabic text direction in this recognition pack is not yet verified. Use standard recognition.")
        if self._engine is not None:
            return self._engine
        import onnxruntime
        import rapidocr_onnxruntime
        from openlargeprint.models import ModelIntegrityError, ModelManager, PINNED_MODELS

        root = Path(rapidocr_onnxruntime.__file__).parent / "models"
        rec_key = "PP-OCRv6_rec_medium"
        paths = {"Det": (root / "ch_PP-OCRv4_det_infer.onnx", "ch_PP-OCRv4_det"),
                 "Cls": (root / "ch_ppocr_mobile_v2.0_cls_infer.onnx", "ch_ppocr_mobile_v2.0_cls"),
                 "Rec": (Path(self.rec_model_path), rec_key)}
        for path, key in paths.values():
            if ModelManager.compute_sha256(path) != PINNED_MODELS.models[key].sha256:
                raise ModelIntegrityError("A recognition model failed integrity verification. Prepare the model pack again.")

        # Missing embedded dictionaries cause upstream to download a fallback.
        # Inspect a verified CPU session before the optional runtime is constructed.
        session = onnxruntime.InferenceSession(str(paths["Rec"][0]), providers=["CPUExecutionProvider"])
        characters = session.get_modelmeta().custom_metadata_map.get("character", "").splitlines()
        output_shape = session.get_outputs()[0].shape
        if not characters or not output_shape or output_shape[-1] != len(characters) + 2:
            raise ModelIntegrityError("The recognition model has an incompatible embedded dictionary.")
        del session
        from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
        threads = min(8, max(1, (os.cpu_count() or 4) - 1))
        params = {
            "Global.log_level": "error",
            **{f"{stage}.model_path": str(path) for stage, (path, _) in paths.items()},
            "Det.ocr_version": OCRVersion.PPOCRV4, "Det.model_type": ModelType.MOBILE,
            "Cls.ocr_version": OCRVersion.PPOCRV4, "Cls.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV6,
            "Rec.model_type": ModelType.MEDIUM,
            "Rec.lang_type": LangRec.CH,
            "EngineConfig.onnxruntime.intra_op_num_threads": threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "EngineConfig.onnxruntime.use_cuda": False,
            "EngineConfig.onnxruntime.use_dml": False,
            "EngineConfig.onnxruntime.use_cann": False,
            "EngineConfig.onnxruntime.use_coreml": False,
        }
        self._engine = RapidOCR(params=params)
        return self._engine

    def analyze_page(self, image: Image.Image, *, page_num: int,
                     language_hints: tuple[str, ...] = ("en",),
                     cancellation: CancellationToken | None = None) -> EnginePageResult:
        return self._worker.analyze_page(image, page_num=page_num,
                                        language_hints=language_hints, cancellation=cancellation)

    def _analyze_page(self, image: Image.Image, *, page_num: int,
                      language_hints: tuple[str, ...] = ("en",),
                      cancellation: CancellationToken | None = None) -> EnginePageResult:
        if cancellation is not None and cancellation.is_cancelled():
            return EnginePageResult(lines=[], cancelled=True)
        start = time.perf_counter()
        engine = self._get_engine()
        import numpy as np
        result = engine(np.asarray(image.convert("RGB")))
        lines, warnings = [], []
        boxes, texts, scores = result.boxes, result.txts, result.scores
        if boxes is None and texts is None and scores is None:
            return EnginePageResult(lines=[], elapse_seconds=time.perf_counter() - start)
        if boxes is None or texts is None or scores is None or not (len(boxes) == len(texts) == len(scores)):
            raise RuntimeError("Recognition returned incomplete results. The original page is retained for review.")
        for box, text, score in zip(boxes, texts, scores):
            if cancellation is not None and cancellation.is_cancelled():
                return EnginePageResult(lines=lines, cancelled=True, warnings=warnings)
            polygon = [(float(point[0]), float(point[1])) for point in box]
            confidence = float(score)
            if len(polygon) != 4 or not all(math.isfinite(v) for point in polygon for v in point) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise RuntimeError("Recognition returned invalid geometry. The original page is retained for review.")
            if text:
                lines.append(OcrDetectedLine(text=str(text), polygon=polygon, confidence=confidence))
                if confidence < 0.6:
                    warnings.append(f"Low confidence recognition on page {page_num}")
        return EnginePageResult(lines=lines, warnings=warnings, elapse_seconds=time.perf_counter() - start)
