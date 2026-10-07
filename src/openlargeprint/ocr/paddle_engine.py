"""PaddleOCR recognition on the CPU through RapidOCR 3 (OCR-001, OCR-002, OCR-006).

Latin-script text uses PP-OCRv6 small detection and recognition, which ship
inside the RapidOCR wheel. Arabic uses the PP-OCRv5 Arabic recognizer with the
same detector. Every model file is checked against the pinned manifest before
it is loaded (SEC-006), and recognition runs in an isolated worker process that
cannot open network connections (SEC-008, SEC-009).
"""

from __future__ import annotations

import math
import os
import time
import unicodedata
from typing import List, Optional, Tuple

from PIL import Image

from openlargeprint.security.isolation import log_safe_info
from .base import CancellationToken, EngineCapabilities, EnginePageResult, OcrDetectedLine, OcrWord
from .worker import OcrWorker

MAX_CPU_THREADS = 8
LOW_CONFIDENCE = 0.60


def _is_arabic(ch: str) -> bool:
    return "؀" <= ch <= "ۿ" or "ݐ" <= ch <= "ݿ" or "ﭐ" <= ch <= "﷿" or "ﹰ" <= ch <= "﻿"


def arabic_visual_to_logical(text: str) -> str:
    """Convert recogniser output from image order to reading order.

    CTC recognisers read a line left to right, so Arabic comes out in visual
    order. This is the same deterministic step PaddleOCR applies to its Arabic
    models (``pred_reverse``): the line is reversed, and runs of non-Arabic
    characters (digits, Latin words) are kept in their original direction.
    """
    runs: List[str] = []
    current = ""
    for ch in text:
        if _is_arabic(ch) or ch in " ،؛؟":
            if current and not (_is_arabic(current[-1]) or current[-1] in " ،؛؟"):
                runs.append(current)
                current = ""
            current += ch
        else:
            if current and (_is_arabic(current[-1]) or current[-1] in " ،؛؟"):
                runs.append(current[::-1])
                current = ""
            current += ch
    if current:
        runs.append(current[::-1] if (_is_arabic(current[-1]) or current[-1] in " ،؛؟") else current)
    return "".join(reversed(runs)).strip()


class PaddleRapidOcrEngine:
    """CPU recogniser adapter; the heavy work happens in the isolated worker."""

    def __init__(self, use_gpu: bool = False, language: str = "en",
                 rec_model_path: Optional[str] = None, rec_keys_path: Optional[str] = None):
        if language not in ("en", "ar"):
            raise ValueError("Unsupported recognition language.")
        self.use_gpu = False  # CPU only: the default path never depends on a GPU (PERF-001)
        self.language = language
        self.rec_model_path = rec_model_path
        self.rec_keys_path = rec_keys_path
        self._engine = None
        self._worker = OcrWorker(use_gpu=False, language=language)

    def close(self) -> None:
        self._worker.close()

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            engine_name="PP-OCRv5 Arabic" if self.language == "ar" else "PP-OCRv6",
            supports_layout=False,
            supports_confidence=True,
            supported_languages=["ar"] if self.language == "ar" else ["en", "fr", "de", "es", "it", "pt", "zh"],
            is_gpu_accelerated=False,
        )

    # -- worker side -----------------------------------------------------
    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        from openlargeprint.models import model_manager
        from rapidocr import LangCls, LangRec, ModelType, OCRVersion, RapidOCR

        det = model_manager.get_model_path("PP-OCRv6_det_small", verify=True)
        cls = model_manager.get_model_path("ch_ppocr_mobile_v2.0_cls", verify=True)
        threads = min(MAX_CPU_THREADS, max(1, (os.cpu_count() or 4) - 1))
        params = {
            "Global.log_level": "error",
            "Global.use_cls": True,
            "Det.model_path": str(det),
            "Det.ocr_version": OCRVersion.PPOCRV6, "Det.model_type": ModelType.SMALL,
            "Cls.model_path": str(cls),
            "Cls.ocr_version": OCRVersion.PPOCRV4, "Cls.model_type": ModelType.MOBILE,
            "Cls.lang_type": LangCls.CH,
            "EngineConfig.onnxruntime.intra_op_num_threads": threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
        if self.language == "ar":
            rec = model_manager.get_model_path("arabic_PP-OCRv5_rec_mobile", verify=True)
            params.update({"Rec.model_path": str(rec), "Rec.ocr_version": OCRVersion.PPOCRV5,
                           "Rec.model_type": ModelType.MOBILE, "Rec.lang_type": LangRec.ARABIC})
        else:
            rec = model_manager.get_model_path("PP-OCRv6_rec_small", verify=True)
            params.update({"Rec.model_path": str(rec), "Rec.ocr_version": OCRVersion.PPOCRV6,
                           "Rec.model_type": ModelType.SMALL})
        log_safe_info(f"Initializing CPU recognizer ({threads} threads)")
        self._engine = RapidOCR(params=params)
        return self._engine

    def analyze_page(self, image: Image.Image, *, page_num: int,
                     language_hints: Tuple[str, ...] = ("en",),
                     cancellation: Optional[CancellationToken] = None) -> EnginePageResult:
        return self._worker.analyze_page(image, page_num=page_num,
                                         language_hints=language_hints, cancellation=cancellation)

    def _analyze_page(self, image: Image.Image, *, page_num: int,
                      language_hints: Tuple[str, ...] = ("en",),
                      cancellation: Optional[CancellationToken] = None) -> EnginePageResult:
        if cancellation is not None and cancellation.is_cancelled():
            return EnginePageResult(lines=[], cancelled=True)
        import numpy as np

        engine = self._get_engine()
        start = time.perf_counter()
        result = engine(np.asarray(image.convert("RGB")), return_word_box=True)
        boxes, texts, scores = result.boxes, result.txts, result.scores
        if boxes is None or texts is None or scores is None:
            return EnginePageResult(lines=[], elapse_seconds=time.perf_counter() - start)
        if not len(boxes) == len(texts) == len(scores):
            raise RuntimeError(f"Recognition returned incomplete results on page {page_num}.")
        word_results = list(result.word_results or ())
        lines: List[OcrDetectedLine] = []
        warnings: List[str] = []
        for index, (box, text, score) in enumerate(zip(boxes, texts, scores)):
            polygon = [(float(p[0]), float(p[1])) for p in box]
            confidence = float(score)
            if len(polygon) != 4 or not all(math.isfinite(v) for p in polygon for v in p):
                continue
            clean = unicodedata.normalize("NFC", str(text)).strip()
            if not clean:
                continue
            words: List[OcrWord] = []
            if self.language == "ar":
                clean = arabic_visual_to_logical(clean)
            elif index < len(word_results):
                for item in word_results[index] or ():
                    try:
                        word_text, word_score, word_box = item
                        words.append(OcrWord(text=str(word_text),
                                             polygon=[(float(p[0]), float(p[1])) for p in word_box],
                                             confidence=float(word_score)))
                    except (TypeError, ValueError):
                        continue
            lines.append(OcrDetectedLine(text=clean, polygon=polygon,
                                         confidence=max(0.0, min(1.0, confidence)), words=words))
            if confidence < LOW_CONFIDENCE:
                warnings.append(f"Low confidence recognition on page {page_num}")
        return EnginePageResult(lines=lines, warnings=warnings,
                                elapse_seconds=time.perf_counter() - start)
