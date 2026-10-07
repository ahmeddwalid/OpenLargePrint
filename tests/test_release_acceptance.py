"""Public release acceptance must describe these exact signed artifacts."""
import importlib.util
from pathlib import Path
import hashlib
import pytest

SPEC = importlib.util.spec_from_file_location("acceptance", Path(__file__).parents[1] / "packaging/release_acceptance.py")


def test_gate_rejects_missing_or_failed_acceptance(tmp_path):
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    installer = tmp_path / "setup.exe"
    portable = tmp_path / "portable.zip"
    installer.write_bytes(b"signed installer fixture")
    portable.write_bytes(b"signed payload fixture")
    record = {"enforced": True, "tested_by": "Release reviewer", "tested_at": "2026-10-02",
        "evidence_url": "https://github.com/example/repo/actions/runs/1",
        "signing_thumbprint": "a" * 40, "uninstaller_sha256": "b" * 64,
        "installer_sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
        "portable_sha256": hashlib.sha256(portable.read_bytes()).hexdigest(),
        "checks": {key: True for key in module.REQUIRED_CHECKS}}
    module.verify_acceptance(record, installer, portable, "a" * 40)
    record["checks"]["installed_uninstaller"] = False
    with pytest.raises(ValueError):
        module.verify_acceptance(record, installer, portable, "a" * 40)
    record["checks"]["installed_uninstaller"] = True
    installer.write_bytes(b"a different build")
    with pytest.raises(ValueError):
        module.verify_acceptance(record, installer, portable, "a" * 40)


def test_publication_waits_for_tested_packages_and_checksums():
    """Nothing is published unless both platforms built, converted documents, and were checksummed."""
    workflow = (Path(__file__).parents[1] / ".github/workflows/release.yml").read_text()
    assert "needs: [version-check, build-windows, build-linux]" in workflow
    assert workflow.count("packaging/smoke_convert.py") >= 3  # installed, portable, AppImage
    assert workflow.index("sha256sum OpenLargePrint* > SHA256SUMS.txt") < workflow.index("softprops/action-gh-release")
    assert "fail_on_unmatched_files: true" in workflow
    assert "permissions:\n  contents: read" in workflow  # write access only in the publish job
