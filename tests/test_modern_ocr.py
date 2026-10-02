"""Optional CPU recognition boundaries (OCR-001..004, LANG-002, SEC-006/009)."""
import importlib
import sys
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from openlargeprint.models import ModelIntegrityError, ModelManager, PINNED_MODELS
from openlargeprint.ocr.base import CancellationToken


def adapter_type():
    assert importlib.util.find_spec("openlargeprint.ocr.modern_engine") is not None, "Optional adapter is missing"
    return importlib.import_module("openlargeprint.ocr.modern_engine").ModernRapidOcrEngine


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    baseline = tmp_path / "baseline"
    (baseline / "models").mkdir(parents=True)
    for name in ("ch_PP-OCRv4_det", "ch_ppocr_mobile_v2.0_cls"):
        (baseline / "models" / f"{name}_infer.onnx").write_bytes(b"test")
    rec = tmp_path / "rec.onnx"
    rec.write_bytes(b"test")
    state = SimpleNamespace(metadata={"character": "a\nb"}, vocabulary=4, constructed=False, bad=False)
    def digest(path):
        key = Path(path).name.removesuffix("_infer.onnx")
        if key == "rec.onnx":
            key = state.key
        return "0" * 64 if state.bad else PINNED_MODELS.models[key].sha256
    monkeypatch.setattr(ModelManager, "compute_sha256", staticmethod(digest))
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", SimpleNamespace(__file__=str(baseline / "__init__.py")))
    class Session:
        def __init__(self, *args, **kwargs): pass
        def get_modelmeta(self): return SimpleNamespace(custom_metadata_map=state.metadata)
        def get_outputs(self): return [SimpleNamespace(shape=[None, None, state.vocabulary])]
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(InferenceSession=Session))
    class Rapid:
        def __init__(self, *, params):
            state.constructed = True
            for stage in ("Det", "Cls", "Rec"):
                for field in ("ocr_version", "model_type"):
                    if not isinstance(params[f"{stage}.{field}"], Enum):
                        raise TypeError("RapidOCR requires enum configuration")
            assert all(params[f"{stage}.model_path"] for stage in ("Det", "Cls", "Rec"))
            assert getattr(params["Rec.lang_type"], "value", params["Rec.lang_type"]) == "ch"
            assert params["EngineConfig.onnxruntime.use_cuda"] is False
        def __call__(self, image):
            return SimpleNamespace(boxes=[[[0, 0], [10, 0], [10, 10], [0, 10]]], txts=("قانون 123",), scores=(0.9,))
    monkeypatch.setitem(sys.modules, "rapidocr", SimpleNamespace(
        RapidOCR=Rapid, OCRVersion=Enum("OCRVersion", {"PPOCRV4": "PP-OCRv4", "PPOCRV5": "PP-OCRv5", "PPOCRV6": "PP-OCRv6"}),
        ModelType=Enum("ModelType", {"MOBILE": "mobile", "MEDIUM": "medium"}),
        LangRec=Enum("LangRec", {"CH": "ch"})))
    state.key = "PP-OCRv6_rec_medium"
    return state, rec


@pytest.mark.parametrize("language,key", [("en", "PP-OCRv6_rec_medium")])
def test_local_optional_recognition_preserves_unicode(runtime, language, key):
    state, rec = runtime
    state.key = key
    engine = adapter_type()(str(rec), language=language)
    try:
        result = engine._analyze_page(Image.new("RGB", (20, 20)), page_num=1)
        assert result.lines[0].text == "قانون 123"
        assert result.lines[0].confidence == 0.9
        assert engine.capabilities().supports_layout is False
        assert engine.capabilities().is_gpu_accelerated is False
    finally:
        engine.close()


@pytest.mark.parametrize("failure", ["hash", "dictionary", "vocabulary"])
def test_invalid_model_cannot_initialize_downloading_runtime(runtime, failure):
    state, rec = runtime
    if failure == "hash": state.bad = True
    elif failure == "dictionary": state.metadata = {}
    else: state.vocabulary = 99
    engine = adapter_type()(str(rec))
    with pytest.raises(ModelIntegrityError):
        engine._get_engine()
    assert state.constructed is False
    engine.close()


def test_cancelled_optional_page_never_initializes_runtime(runtime):
    state, rec = runtime
    token = CancellationToken()
    token.cancel()
    engine = adapter_type()(str(rec))
    assert engine._analyze_page(Image.new("RGB", (20, 20)), page_num=1, cancellation=token).cancelled
    assert state.constructed is False
    engine.close()


def test_worker_rejects_unregistered_backend():
    from openlargeprint.ocr.worker import OcrWorker
    with pytest.raises(ValueError):
        OcrWorker(use_gpu=False, backend="untrusted")


def test_unverified_visual_arabic_output_is_not_accepted_as_logical_text(runtime):
    state, rec = runtime
    state.key = "arabic_PP-OCRv5_rec_mobile"
    engine = adapter_type()(str(rec), language="ar")
    with pytest.raises(RuntimeError, match="direction"):
        engine._analyze_page(Image.new("RGB", (20, 20)), page_num=1)
    assert not state.constructed
    assert "ar" not in engine.capabilities().supported_languages
    engine.close()
