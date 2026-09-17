"""Tests for LibreOfficeBridge legacy DOC/PPT conversion (OFF-002, OFF-003, SEC-008)."""

from pathlib import Path
from unittest.mock import patch
import pytest

from openlargeprint.importers.office.legacy_bridge import LibreOfficeBridge
from openlargeprint.security import JobWorkspace


def test_find_libreoffice_binary():
    """Verify LibreOffice or soffice is discoverable on PATH."""
    bin_path = LibreOfficeBridge.find_libreoffice_binary()
    assert bin_path is not None, "LibreOffice executable should be found on test environment"
    assert any(name in bin_path for name in ("libreoffice", "soffice"))


def test_legacy_bridge_conversion_real_doc(tmp_path: Path):
    """Verify headless LibreOffice converts a document into a modern intermediate (OFF-002, OFF-003)."""
    bridge = LibreOfficeBridge(timeout_seconds=30)
    lo_bin = bridge.find_libreoffice_binary()
    if not lo_bin:
        pytest.skip("LibreOffice not installed on host machine")

    # Create a simple text file to convert to docx via LibreOffice
    input_txt = tmp_path / "legacy_source.txt"
    input_txt.write_text("Case Report: Donoghue v Stevenson [1932] AC 562.\nEstablished manufacturer duty of care.")

    with JobWorkspace() as ws:
        out_docx = bridge.convert_to_modern(input_txt, "docx", ws)
        assert out_docx.exists()
        assert out_docx.suffix == ".docx"
        assert out_docx.stat().st_size > 0
        # Ensure disposable profile was created in workspace
        profile_dir = ws.path / "lo_disposable_profile"
        assert profile_dir.exists()


def test_legacy_bridge_missing_binary(tmp_path: Path):
    """Verify informative error if LibreOffice binary is missing."""
    bridge = LibreOfficeBridge()
    fake_doc = tmp_path / "sample.doc"
    fake_doc.write_bytes(b"dummy")

    with patch.object(LibreOfficeBridge, "find_libreoffice_binary", return_value=None):
        with JobWorkspace() as ws:
            with pytest.raises(RuntimeError, match="LibreOffice is required"):
                bridge.convert_to_modern(fake_doc, "docx", ws)


def test_legacy_bridge_missing_input_file():
    """Verify FileNotFoundError if input document does not exist."""
    bridge = LibreOfficeBridge()
    with JobWorkspace() as ws:
        with pytest.raises(FileNotFoundError):
            bridge.convert_to_modern(Path("/non/existent/legacy.doc"), "docx", ws)


def test_legacy_bridge_timeout(tmp_path: Path):
    """Verify timeout terminates process tree and raises TimeoutError (SEC-008)."""
    # Use extremely short timeout to trigger TimeoutError
    bridge = LibreOfficeBridge(timeout_seconds=0.0001)
    lo_bin = bridge.find_libreoffice_binary()
    if not lo_bin:
        pytest.skip("LibreOffice not installed on host machine")

    input_file = tmp_path / "test.txt"
    input_file.write_text("Hello World")

    with JobWorkspace() as ws:
        with pytest.raises(TimeoutError, match="exceeded timeout limit"):
            bridge.convert_to_modern(input_file, "docx", ws)
