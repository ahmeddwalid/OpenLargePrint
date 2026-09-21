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


def test_default_engine_is_cpu_only():
    """Default orchestrator must instantiate a CPU-only engine (PERF-001, OCR-006)."""
    from openlargeprint.pipeline import PipelineOrchestrator

    orch = PipelineOrchestrator()
    assert orch.routing_mode == RoutingMode.AUTOMATIC
    router = OcrRouter()
    engine = router.get_engine()
    assert isinstance(engine, DocumentOcrEngine)
    # Default fast engine must not request GPU
    assert getattr(engine, "use_gpu", False) is False


def test_routing_mode_matrix():
    """AUTOMATIC/FAST return CPU engine; MAXIMUM tries VLM then falls back (OCR-001)."""
    router = OcrRouter()
    auto_eng = router.get_engine(RoutingMode.AUTOMATIC)
    fast_eng = router.get_engine(RoutingMode.FAST)
    assert type(auto_eng) is type(fast_eng)
    assert getattr(auto_eng, "use_gpu", False) is False
    max_eng = router.get_engine(RoutingMode.MAXIMUM_ACCURACY)
    assert isinstance(max_eng, DocumentOcrEngine)
    # Without the optional VLM model installed, MAXIMUM falls back to CPU engine
    from openlargeprint.ocr.paddle_engine import PaddleRapidOcrEngine

    try:
        from openlargeprint.ocr.vlm_engine import PaddleOcrVlEngine

        assert isinstance(max_eng, (PaddleRapidOcrEngine, PaddleOcrVlEngine))
    except ImportError:
        assert isinstance(max_eng, PaddleRapidOcrEngine)


def test_engine_swap_distinct_classes_when_vlm_available(monkeypatch):
    """FAST vs MAXIMUM return different classes when VLM model is present (OCR-001)."""
    from openlargeprint.ocr.paddle_engine import PaddleRapidOcrEngine
    from openlargeprint.ocr.vlm_engine import PaddleOcrVlEngine

    # Fake model_manager.get_model_path to succeed
    import openlargeprint.models.manager as mgr_mod

    def fake_get(key, verify=True):
        from pathlib import Path

        return Path("/tmp/fake-vlm.onnx")

    monkeypatch.setattr(mgr_mod.model_manager, "get_model_path", fake_get)
    router = OcrRouter()
    fast_eng = router.get_engine(RoutingMode.FAST)
    max_eng = router.get_engine(RoutingMode.MAXIMUM_ACCURACY)
    assert isinstance(fast_eng, PaddleRapidOcrEngine)
    assert isinstance(max_eng, PaddleOcrVlEngine)
    assert type(fast_eng) is not type(max_eng)


def test_ocr_cancellation_token():
    """A tripped CancellationToken must short-circuit OCR without full run (UI-002)."""
    from PIL import Image
    from openlargeprint.ocr import CancellationToken

    img = Image.new("RGB", (500, 120), color="white")
    token = CancellationToken()
    token.cancel()
    assert bool(token) is True
    engine = PaddleRapidOcrEngine()
    result = engine.analyze_page(img, page_num=1, cancellation=token)
    assert result.cancelled is True
    assert result.lines == []


def test_cpu_thread_limits_reach_runtime():
    from openlargeprint.ocr.paddle_engine import MAX_CPU_THREADS, INTER_OP_THREADS

    engine = PaddleRapidOcrEngine(use_gpu=False)._get_engine()
    for adapter in (engine.text_det.infer, engine.text_cls.infer, engine.text_rec.session):
        session = adapter.session
        options = session.get_session_options()
        assert 1 <= options.intra_op_num_threads <= MAX_CPU_THREADS
        assert options.inter_op_num_threads == INTER_OP_THREADS
        assert session.get_providers() == ["CPUExecutionProvider"]
