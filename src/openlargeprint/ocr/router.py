"""OCR engine router supporting Automatic, Fast, and Maximum accuracy modes (DESIGN.md §4)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional
from .base import DocumentOcrEngine
from .paddle_engine import PaddleRapidOcrEngine


class RoutingMode(str, Enum):
    """Routing modes exposed behind Advanced options (UI-001, DESIGN.md §4)."""
    AUTOMATIC = "Automatic"
    FAST = "Fast"
    MAXIMUM_ACCURACY = "Maximum accuracy"


class OcrRouter:
    """Routes pages to the appropriate OCR engine based on user preference, language, and availability."""

    def __init__(self):
        self._default_engine: Optional[DocumentOcrEngine] = None
        self._arabic_engine: Optional[DocumentOcrEngine] = None

    def close(self) -> None:
        """Release every routed recognizer's disposable worker (SEC-004/008)."""
        seen = set()
        for engine in (self._default_engine, self._arabic_engine):
            if engine is not None and id(engine) not in seen:
                seen.add(id(engine))
                close = getattr(engine, "close", None)
                if callable(close):
                    close()

    def get_engine(
        self,
        mode: RoutingMode = RoutingMode.AUTOMATIC,
        language: str = "en",
    ) -> DocumentOcrEngine:
        """Return the OCR engine corresponding to the selected routing mode (default: Automatic) and language."""
        engine = None
        if language == "ar":
            if self._arabic_engine is None:
                self._arabic_engine = self._init_arabic_engine()
            if self._arabic_engine is not None:
                engine = self._arabic_engine

        if engine is None and self._default_engine is None:
            self._default_engine = PaddleRapidOcrEngine(use_gpu=False)
        engine = engine or self._default_engine

        if mode == RoutingMode.MAXIMUM_ACCURACY:
            from .vlm_engine import PaddleOcrVlEngine
            return PaddleOcrVlEngine(fallback=engine)
        elif mode in (RoutingMode.AUTOMATIC, RoutingMode.FAST):
            return engine
        return self.get_engine(RoutingMode.MAXIMUM_ACCURACY, language=language)

    def _init_arabic_engine(self) -> Optional[DocumentOcrEngine]:
        from openlargeprint.models import model_manager, ModelManager
        from openlargeprint.models.manifest import ARABIC_DICTIONARY_SHA256
        try:
            model_path = model_manager.get_model_path("arabic_PP-OCRv3_rec", verify=True)
            dict_path = Path(__file__).resolve().parent.parent / "models" / "languages" / "arabic" / "dict.txt"
            if ModelManager.compute_sha256(dict_path) != ARABIC_DICTIONARY_SHA256:
                return None
            return PaddleRapidOcrEngine(
                use_gpu=False,
                rec_model_path=str(model_path),
                rec_keys_path=str(dict_path),
                language="ar",
            )
        except Exception:
            return None

