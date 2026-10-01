"""Development must not silently launch a stale frozen engine (PKG-002)."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "packaging" / "sidecar_freshness.py"
spec = importlib.util.spec_from_file_location("sidecar_freshness", path)


def test_fingerprint_changes_with_source_and_binary(tmp_path):
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "src/openlargeprint").mkdir(parents=True)
    source = tmp_path / "src/openlargeprint/version.py"
    source.write_text("first")
    binary = tmp_path / "engine.exe"
    binary.write_bytes(b"old")
    module.record_build(tmp_path, binary)
    assert module.is_fresh(tmp_path, binary)
    source.write_text("second")
    assert not module.is_fresh(tmp_path, binary)
    module.record_build(tmp_path, binary)
    binary.write_bytes(b"tampered")
    assert not module.is_fresh(tmp_path, binary)
def test_onefile_build_refuses_missing_output(tmp_path, monkeypatch):
    import importlib.util
    import sys
    import pytest
    packaging_dir = Path(__file__).parents[1] / "packaging"
    monkeypatch.syspath_prepend(str(packaging_dir))
    spec = importlib.util.spec_from_file_location("build_sidecar_test", packaging_dir / "build_sidecar.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "packaging/build_sidecar.py"))
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["build_sidecar.py"])
    with pytest.raises(RuntimeError, match="expected executable"):
        module.build_sidecar()
