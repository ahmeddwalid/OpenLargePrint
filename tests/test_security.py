"""Tests for security, validation, and isolation (SEC-001, SEC-003, SEC-004, SEC-007, SEC-009)."""

import socket
from pathlib import Path
import pytest
from openlargeprint.security import (
    JobWorkspace,
    SecurityValidationError,
    detect_file_type,
    log_safe_info,
    validate_image_dimensions,
)


def test_detect_file_type_valid_pdf(tmp_path: Path):
    """Verify that a genuine PDF header is detected regardless of extension (SEC-001)."""
    pdf_file = tmp_path / "document.dat"  # Non-.pdf extension
    pdf_file.write_bytes(b"%PDF-1.7\n%some content here")
    detected = detect_file_type(pdf_file)
    assert detected == "pdf"


def test_detect_file_type_rejects_spoofed_extension(tmp_path: Path):
    """Verify that an arbitrary file renamed to .pdf is rejected (SEC-001)."""
    fake_pdf = tmp_path / "malicious.pdf"
    fake_pdf.write_text("This is just a plain text script, not a PDF.")
    with pytest.raises(SecurityValidationError, match="File format not recognized"):
        detect_file_type(fake_pdf)


def test_detect_file_type_rejects_empty_file(tmp_path: Path):
    """Verify empty file is rejected."""
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")
    with pytest.raises(SecurityValidationError, match="The file is empty"):
        detect_file_type(empty_file)


def test_validate_image_dimensions_bounds():
    """Verify bounds enforcement on raster dimensions (SEC-003)."""
    # Valid dimensions
    validate_image_dimensions(1920, 1080)

    # Exceeds max single dimension
    with pytest.raises(SecurityValidationError, match="exceed safety limit"):
        validate_image_dimensions(15000, 500)

    # Exceeds total pixel count (8000x8000 = 64 MP > 50 MP)
    with pytest.raises(SecurityValidationError, match="total pixels"):
        validate_image_dimensions(8000, 8000)


def test_job_workspace_creates_and_cleans_up():
    """Verify that JobWorkspace creates an isolated temporary directory and cleans up on exit (SEC-004)."""
    created_path = None
    created_assets = None
    with JobWorkspace() as ws:
        created_path = ws.path
        created_assets = ws.assets_dir
        assert created_path is not None
        assert created_path.exists()
        assert created_assets.exists()

        # Create a test file in the workspace
        test_file = created_path / "test.txt"
        test_file.write_text("temporary data")
        assert test_file.exists()

    # After exiting context manager, directory must be completely removed
    assert not created_path.exists()


def test_zero_network_traffic_during_operation(monkeypatch):
    """Verify that no socket connection calls are permitted (SEC-009)."""
    def no_socket_connect(*args, **kwargs):
        raise AssertionError("Network connection attempted! SEC-009 violation.")

    monkeypatch.setattr(socket.socket, "connect", no_socket_connect)

    # Logging and workspace execution should not invoke network calls
    with JobWorkspace() as ws:
        log_safe_info("Running local conversion step")
        assert ws.path.exists()
