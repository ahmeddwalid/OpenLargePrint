"""Tests for model artifact management, integrity verification, and offline checks (SEC-006, SEC-009)."""

import hashlib
from pathlib import Path
import pytest

from openlargeprint.models import (
    ModelArtifact,
    ModelCatalog,
    ModelFramework,
    ModelIntegrityError,
    ModelManager,
    ModelTask,
    PINNED_MODELS,
)


def test_model_catalog_defaults():
    """Verify pinned model catalog includes required default models."""
    defaults = PINNED_MODELS.list_defaults()
    assert "ch_PP-OCRv4_det" in defaults
    assert "ch_PP-OCRv4_rec" in defaults
    assert "ch_ppocr_mobile_v2.0_cls" in defaults
    assert len(defaults) == 3
    assert "paddleocr_vl_1.6" not in PINNED_MODELS.models


def test_model_cache_dir_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify OPENLARGEPRINT_MODEL_DIR environment override."""
    custom_dir = tmp_path / "custom_models"
    monkeypatch.setenv("OPENLARGEPRINT_MODEL_DIR", str(custom_dir))

    mgr = ModelManager()
    assert mgr.cache_dir == custom_dir
    assert custom_dir.exists()


def test_model_sha256_verification_and_tamper_detection(tmp_path: Path):
    """Verify SHA-256 verification rejects tampered weights (SEC-006)."""
    fake_weights = b"VERIFIED_ONNX_MODEL_WEIGHTS_v1.0"
    correct_hash = hashlib.sha256(fake_weights).hexdigest()

    test_catalog = ModelCatalog(
        models={
            "test_model": ModelArtifact(
                key="test_model",
                name="Test Model",
                task=ModelTask.RECOGNITION,
                framework=ModelFramework.ONNX,
                version="1.0.0",
                sha256=correct_hash,
                file_size_bytes=len(fake_weights),
                code_license="Apache-2.0",
                weight_license="Apache-2.0",
            )
        }
    )

    mgr = ModelManager(catalog=test_catalog, cache_dir=tmp_path)

    # 1. Install genuine model file
    src_file = tmp_path / "src_model.onnx"
    src_file.write_bytes(fake_weights)
    installed_path = mgr.install_model("test_model", src_file)
    assert installed_path.exists()

    # 2. Successfully load verified model path
    verified = mgr.get_model_path("test_model", verify=True)
    assert verified == installed_path

    # 3. Tamper with the installed file and verify rejection
    installed_path.write_bytes(b"TAMPERED_MALICIOUS_DATA")
    with pytest.raises(ModelIntegrityError) as exc_info:
        mgr.get_model_path("test_model", verify=True)
    assert "failed integrity verification" in str(exc_info.value)


def test_model_manager_offline_readiness(tmp_path: Path):
    """Verify offline readiness check indicates when models are present vs missing (SEC-009)."""
    dummy_bytes = b"MODEL_DUMMY_PAYLOAD"
    dummy_hash = hashlib.sha256(dummy_bytes).hexdigest()

    catalog = ModelCatalog(
        models={
            "m1": ModelArtifact(
                key="m1",
                name="Model 1",
                task=ModelTask.DETECTION,
                framework=ModelFramework.ONNX,
                version="1.0",
                sha256=dummy_hash,
                file_size_bytes=len(dummy_bytes),
                code_license="MIT",
                weight_license="MIT",
                is_default=True,
            )
        }
    )

    mgr = ModelManager(catalog=catalog, cache_dir=tmp_path)

    # Initially false because m1 is not installed
    assert not mgr.is_offline_ready(["m1"])

    # Install m1
    m1_src = tmp_path / "m1_src.onnx"
    m1_src.write_bytes(dummy_bytes)
    mgr.install_model("m1", m1_src)

    # Now offline ready
    assert mgr.is_offline_ready(["m1"])


def test_download_model_verifies_hash(tmp_path: Path):
    """download_model must fetch bytes and verify pinned SHA-256 (OCR-003, SEC-006)."""
    import functools
    import hashlib
    import http.server
    import threading

    payload = b"FAKE_ONNX_BYTES_FOR_TEST"
    digest = hashlib.sha256(payload).hexdigest()
    serve_dir = tmp_path / "serve"
    serve_dir.mkdir()
    (serve_dir / "model.onnx").write_bytes(payload)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(serve_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/model.onnx"
        catalog = ModelCatalog(
            models={
                "dl_model": ModelArtifact(
                    key="dl_model",
                    name="Downloadable Test Model",
                    task=ModelTask.RECOGNITION,
                    framework=ModelFramework.ONNX,
                    version="1.0",
                    sha256=digest,
                    file_size_bytes=len(payload),
                    code_license="Apache-2.0",
                    weight_license="Apache-2.0",
                    download_url=url,
                )
            }
        )
        cache = tmp_path / "cache"
        mgr = ModelManager(catalog=catalog, cache_dir=cache)
        dest = mgr.download_model("dl_model")
        assert dest.exists()
        assert dest.read_bytes() == payload
        # Second call without force returns cached verified path
        assert mgr.download_model("dl_model") == dest
    finally:
        server.shutdown()
        thread.join(timeout=5)
