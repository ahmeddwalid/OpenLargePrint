"""Tests for security hardening, active content stripping, zip bombs, and offline isolation (SEC-001..009)."""

import io
from pathlib import Path
import socket
import zipfile
import pikepdf
import pytest
from reportlab.pdfgen import canvas

from openlargeprint.pipeline import PipelineOrchestrator
from openlargeprint.security import (
    SecurityValidationError,
    log_safe_info,
    safe_extract_zip,
    sanitize_document,
    sanitize_office_openxml,
    sanitize_pdf,
)
from test_docx_importer import create_sample_docx


def test_sanitize_pdf_strips_javascript(tmp_path: Path):
    """Verify PDF active content (JavaScript, Launch actions) is neutralized (SEC-002)."""
    pdf_path = tmp_path / "with_js.pdf"
    clean_path = tmp_path / "sanitized.pdf"

    # Create PDF with embedded JavaScript
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(595, 842))

    # Add JavaScript dictionary to Root.Names
    js_dict = pikepdf.Dictionary({
        "/S": pikepdf.Name("/JavaScript"),
        "/JS": pikepdf.String("app.alert('malicious script executed');"),
    })
    pdf.Root["/OpenAction"] = js_dict
    pdf.Root["/Names"] = pikepdf.Dictionary({
        "/JavaScript": pikepdf.Dictionary({}),
    })
    pdf.save(pdf_path)
    pdf.close()

    # Sanitize
    out_file, stripped = sanitize_pdf(pdf_path, clean_path)
    assert out_file.exists()
    assert len(stripped) >= 1
    assert any("OpenAction" in s or "JavaScript" in s for s in stripped)

    # Inspect sanitized PDF
    sanitized_pdf = pikepdf.open(clean_path)
    assert "/OpenAction" not in sanitized_pdf.Root
    if "/Names" in sanitized_pdf.Root:
        assert "/JavaScript" not in sanitized_pdf.Root.Names
    sanitized_pdf.close()


def test_sanitize_office_strips_vba_macros(tmp_path: Path):
    """Verify Office VBA macros and active content are stripped (SEC-002)."""
    docx_path = tmp_path / "macro_document.docx"
    clean_path = tmp_path / "sanitized_doc.docx"

    # Create valid minimal docx archive with an added vbaProject.bin member
    with zipfile.ZipFile(docx_path, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Legal Text</w:t></w:r></w:p></w:body></w:document>')
        zf.writestr("word/vbaProject.bin", b"VBA_MACRO_BYTECODE_PAYLOAD")
        zf.writestr("word/_rels/document.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')

    out_file, stripped = sanitize_office_openxml(docx_path, clean_path)
    assert out_file.exists()
    assert any("vbaProject.bin" in s for s in stripped)

    with zipfile.ZipFile(clean_path, "r") as zclean:
        names = zclean.namelist()
        assert "word/vbaProject.bin" not in names
        assert "word/document.xml" in names


def test_zip_slip_prevention(tmp_path: Path):
    """Verify zip-slip path traversal archives are rejected (SEC-003)."""
    zip_path = tmp_path / "slip_attack.zip"
    dest_dir = tmp_path / "extract_dest"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../pwned.sh", "echo owned")

    with pytest.raises(SecurityValidationError) as exc_info:
        safe_extract_zip(zip_path, dest_dir)
    assert "Zip-slip path traversal attempt" in str(exc_info.value)


def test_zip_bomb_prevention(tmp_path: Path):
    """Verify archive decompression bombs are rejected (SEC-003)."""
    zip_path = tmp_path / "bomb.zip"
    dest_dir = tmp_path / "extract_dest"

    # Create a 20MB uncompressed file of zeros that compresses to a few bytes
    large_zeros = b"\x00" * (20 * 1024 * 1024)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge_file.dat", large_zeros)

    # Threshold ratio is 100.0x, this file will have ratio > 10,000x
    with pytest.raises(SecurityValidationError) as exc_info:
        safe_extract_zip(zip_path, dest_dir, max_ratio=50.0)
    assert "Decompression bomb detected" in str(exc_info.value)


def test_privacy_log_audit(caplog):
    """Verify logs do not dump arbitrary document contents (SEC-007)."""
    import logging
    caplog.set_level(logging.INFO)

    short_msg = "Safe operation on document job-123 completed."
    log_safe_info(short_msg)
    assert short_msg in caplog.text

    # Extremely long payload should be truncated
    huge_payload = "SECRET_PATIENT_RECORDS_" * 100
    log_safe_info(huge_payload)
    assert "truncated for privacy" in caplog.text


def test_offline_conversion_network_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify standard conversion produces zero network traffic (SEC-009)."""
    # Create input document
    input_pdf = tmp_path / "offline_test.pdf"
    c = canvas.Canvas(str(input_pdf))
    c.drawString(72, 750, "Confidential Client Memorandum")
    c.showPage()
    c.save()

    output_pdf = tmp_path / "offline_out.pdf"

    # Block all network socket connections
    def no_network(*args, **kwargs):
        raise RuntimeError("Illegal network connection attempted during offline conversion! (SEC-009)")

    monkeypatch.setattr(socket.socket, "connect", no_network)

    # Run conversion
    orchestrator = PipelineOrchestrator()
    res = orchestrator.convert(input_pdf, output_pdf, export_format="pdf")

    assert res.success
    assert output_pdf.exists()


def test_offline_conversion_cannot_even_create_a_socket(tmp_path, monkeypatch):
    """No socket may be created and no DNS lookup may run (SEC-009).

    Blocking only socket.connect() still allows a transport to be constructed, or a
    name to be resolved, before the connection fails. This guards the stricter
    property the product promises: the standard conversion path never touches the
    network at all.
    """
    attempts: list[str] = []

    class _BlockedSocket:
        def __init__(self, *args, **kwargs):
            attempts.append("socket.socket")
            raise AssertionError("A socket was created during an offline conversion (SEC-009)")

    def _blocked_getaddrinfo(*args, **kwargs):
        attempts.append("socket.getaddrinfo")
        raise AssertionError("A DNS lookup was attempted during an offline conversion (SEC-009)")

    monkeypatch.setattr(socket, "socket", _BlockedSocket)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked_getaddrinfo)

    input_pdf = tmp_path / "offline_strict.pdf"
    c = canvas.Canvas(str(input_pdf))
    c.drawString(72, 750, "Offline conversion guard")
    c.showPage()
    c.save()

    output_pdf = tmp_path / "offline_strict_out.pdf"
    res = PipelineOrchestrator().convert(input_pdf, output_pdf, export_format="pdf")

    assert res.success
    assert output_pdf.exists()
    assert attempts == []


def test_render_scale_bounds_oversized_pages():
    import math
    from openlargeprint.security.validator import bounded_pdf_scale, validate_image_dimensions, MAX_RENDER_PIXELS

    for width, height in ((595, 842), (1000000, 2000000), (100, 1000000)):
        scale = bounded_pdf_scale(width, height)
        pixels = (math.ceil(width * scale), math.ceil(height * scale))
        validate_image_dimensions(*pixels)
        assert pixels[0] * pixels[1] <= MAX_RENDER_PIXELS
    for width in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            bounded_pdf_scale(width, 842)


def test_job_identifiers_cannot_escape_asset_root(tmp_path):
    from openlargeprint.security.assets import JobAssetStore

    for value in ("../outside", "/tmp/outside", "a/b", "a\\b", "..", "x" * 129):
        with pytest.raises(ValueError):
            JobAssetStore(job_id=value, root=tmp_path)
    assert not list(tmp_path.iterdir())


def test_export_options_reject_unsafe_sizes():
    from openlargeprint.exporters import ExportOptions, PresetName

    for value in (0, -1, float("nan"), float("inf"), True, 100000):
        with pytest.raises(ValueError):
            ExportOptions(preset=PresetName.CUSTOM, custom_body_pt=value)
    assert ExportOptions(preset=PresetName.CUSTOM).body_pt == 20


def test_atomic_export_keeps_previous_output_on_failure(tmp_path):
    from openlargeprint.security.isolation import atomic_output

    destination = tmp_path / "report.pdf"
    destination.write_bytes(b"previous completed report")
    with pytest.raises(RuntimeError):
        with atomic_output(destination) as partial:
            partial.write_bytes(b"incomplete report")
            raise RuntimeError("export failed")
    assert destination.read_bytes() == b"previous completed report"
    assert list(tmp_path.iterdir()) == [destination]


def test_non_object_ipc_input_is_rejected():
    import io
    import json
    from openlargeprint.sidecar.runner import SidecarRunner

    for payload in ("[]", "null", "12", '"convert"'):
        output = io.StringIO()
        runner = SidecarRunner(out_stream=output)
        runner.execute_command_str(payload)
        assert json.loads(output.getvalue())["code"] == "INVALID_COMMAND"
