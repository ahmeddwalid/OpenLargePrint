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
    NATIVE_ONLY = "Native text only"


class OcrRouter:
    """Routes pages to the appropriate OCR engine based on user preference, language, and availability."""

    def __init__(self):
        self._default_engine: Optional[DocumentOcrEngine] = None
        self._arabic_engine: Optional[DocumentOcrEngine] = None
        self._modern_engines: dict[str, DocumentOcrEngine] = {}

    def close(self) -> None:
        """Release every routed recognizer's disposable worker (SEC-004/008)."""
        seen = set()
        for engine in (self._default_engine, self._arabic_engine, *self._modern_engines.values()):
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
        if mode == RoutingMode.MAXIMUM_ACCURACY:
            if language not in self._modern_engines:
                path = self._modern_model_path(language)
                if path is not None:
                    from .modern_engine import ModernRapidOcrEngine
                    self._modern_engines[language] = ModernRapidOcrEngine(str(path), language=language)
            if language in self._modern_engines:
                return self._modern_engines[language]
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
        elif mode in (RoutingMode.AUTOMATIC, RoutingMode.FAST, RoutingMode.NATIVE_ONLY):
            return engine
        return self.get_engine(RoutingMode.MAXIMUM_ACCURACY, language=language)

    @staticmethod
    def _modern_model_path(language: str) -> Path | None:
        import importlib.util
        from importlib.metadata import version, PackageNotFoundError
        from openlargeprint.models import model_manager, ModelIntegrityError
        # Arabic-v5's decoder direction needs mixed-script acceptance before
        # it can enter product routing; verified weights alone are insufficient.
        keys = {"en": "PP-OCRv6_rec_medium"}
        if language not in keys or importlib.util.find_spec("rapidocr") is None:
            return None
        try:
            if version("rapidocr") != "3.9.2":
                return None
            return model_manager.get_model_path(keys[language], verify=True)
        except (OSError, ModelIntegrityError, PackageNotFoundError):
            return None

    @classmethod
    def available_accuracy_languages(cls) -> list[str]:
        return [language for language in ("en", "ar") if cls._modern_model_path(language) is not None]

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

