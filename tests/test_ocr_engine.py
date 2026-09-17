"""Tests for OCR engine abstraction and PaddleOCR adapter (OCR-001, OCR-002, OCR-006)."""

from PIL import Image, ImageDraw
import pytest
from openlargeprint.ocr import (
    DocumentOcrEngine,
    EngineCapabilities,
    OcrRouter,
    PaddleRapidOcrEngine,
    RoutingMode,
)


def test_paddle_engine_conforms_to_protocol():
    """Verify that PaddleRapidOcrEngine implements DocumentOcrEngine protocol."""
    engine = PaddleRapidOcrEngine()
    assert isinstance(engine, DocumentOcrEngine)
    caps = engine.capabilities()
    assert isinstance(caps, EngineCapabilities)
    assert caps.supports_confidence is True
    assert "en" in caps.supported_languages
    assert caps.is_gpu_accelerated is False  # CPU-friendly (OCR-006)


def test_paddle_engine_text_recognition():
    """Verify on-device text recognition on a rendered image (OCR-002, OCR-006)."""
    img = Image.new("RGB", (500, 120), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 40), "Judicial Review in Administrative Law", fill="black")

    engine = PaddleRapidOcrEngine()
    result = engine.analyze_page(img, page_num=1)

    assert len(result.lines) > 0
    first_line = result.lines[0]
    assert "Judicial Review" in first_line.text or "Administrative" in first_line.text
    assert first_line.confidence > 0.70
    assert first_line.width > 0
    assert first_line.height > 0
    assert result.elapse_seconds > 0.0


def test_ocr_router_modes():
    """Verify that OcrRouter returns functional engines for all declared routing modes."""
    router = OcrRouter()
    engine_auto = router.get_engine(RoutingMode.AUTOMATIC)
    engine_fast = router.get_engine(RoutingMode.FAST)
    engine_max = router.get_engine(RoutingMode.MAXIMUM_ACCURACY)

    assert isinstance(engine_auto, DocumentOcrEngine)
    assert isinstance(engine_fast, DocumentOcrEngine)
    assert isinstance(engine_max, DocumentOcrEngine)
