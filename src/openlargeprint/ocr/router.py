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
    """Routes pages to the appropriate OCR engine based on user preference, language, and availability."""

    def __init__(self):
        self._default_engine: Optional[DocumentOcrEngine] = None
        self._arabic_engine: Optional[DocumentOcrEngine] = None

    def get_engine(
        self,
        mode: RoutingMode = RoutingMode.AUTOMATIC,
        language: str = "en",
    ) -> DocumentOcrEngine:
        """Return the OCR engine corresponding to the selected routing mode (default: Automatic) and language."""
        if language == "ar":
            if self._arabic_engine is None:
                self._arabic_engine = self._init_arabic_engine()
            if self._arabic_engine is not None:
                return self._arabic_engine

        if self._default_engine is None:
            self._default_engine = PaddleRapidOcrEngine(use_gpu=False)

        if mode == RoutingMode.MAXIMUM_ACCURACY:
            from .vlm_engine import PaddleOcrVlEngine
            return PaddleOcrVlEngine(fallback=self._default_engine)
        elif mode in (RoutingMode.AUTOMATIC, RoutingMode.FAST):
            return self._default_engine
        return self.get_engine(RoutingMode.MAXIMUM_ACCURACY, language=language)

    def _init_arabic_engine(self) -> Optional[DocumentOcrEngine]:
        from openlargeprint.models import model_manager
        try:
            model_path = model_manager.get_model_path("arabic_PP-OCRv3_rec", verify=True)
            dict_path = model_path.parent / "arabic_dict.txt"
            if not dict_path.exists():
                bundled_dict = (
                    Path(__file__).resolve().parent.parent / "models" / "languages" / "arabic" / "dict.txt"
                )
                if bundled_dict.exists():
                    dict_path = bundled_dict
            keys_arg = str(dict_path) if dict_path.exists() else None
            return PaddleRapidOcrEngine(
                use_gpu=False,
                rec_model_path=str(model_path),
                rec_keys_path=keys_arg,
                language="ar",
            )
        except Exception:
            return None

