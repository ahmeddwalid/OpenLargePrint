"""Unit tests for Sidecar JSON-Lines IPC protocol, cancellation, and review (DESIGN.md §9, UI-002..005)."""

import io
import json
from pathlib import Path
import pypdfium2 as pdfium
import pytest

from openlargeprint.sidecar.protocol import (
    CommandType,
    EventType,
)
from openlargeprint.sidecar.runner import SidecarRunner
from test_docx_importer import create_sample_docx


def create_minimal_pdf(file_path: Path) -> Path:
    """Create a simple 2-page PDF document for testing."""
    pdf = pdfium.PdfDocument.new()
    # Page 1
    p1 = pdf.new_page(595, 842)
    p1.close()
    # Page 2
    p2 = pdf.new_page(595, 842)
    p2.close()
    pdf.save(str(file_path))
    pdf.close()
    return file_path


def test_sidecar_health_check():
    """Verify health check returns ready status and OCR capability."""
    in_buf = io.StringIO('{"command": "health"}\n')
    out_buf = io.StringIO()

    runner = SidecarRunner(in_stream=in_buf, out_stream=out_buf)
    runner.run_loop()

    out_lines = [json.loads(line) for line in out_buf.getvalue().strip().split("\n") if line.strip()]
    assert len(out_lines) == 1
    event = out_lines[0]
    assert event["type"] == EventType.HEALTH.value
    assert event["status"] == "ready"
    assert event["ocr_available"] is True


def test_sidecar_inspect_pdf(tmp_path: Path):
    """Verify inspect command returns document format, page count, and title."""
    pdf_file = tmp_path / "sample.pdf"
    create_minimal_pdf(pdf_file)

    cmd = json.dumps({"command": "inspect", "file_path": str(pdf_file)})
    in_buf = io.StringIO(f"{cmd}\n")
    out_buf = io.StringIO()

    runner = SidecarRunner(in_stream=in_buf, out_stream=out_buf)
    runner.run_loop()

    out_lines = [json.loads(line) for line in out_buf.getvalue().strip().split("\n") if line.strip()]
    assert len(out_lines) == 1
    event = out_lines[0]
    assert event["type"] == EventType.INSPECT_RESULT.value
    assert event["detected_format"] == "pdf"
    assert event["page_count"] == 2
    assert event["file_name"] == "sample.pdf"


def test_sidecar_inspect_classification_summary(tmp_path: Path):
    """Inspect must return per-page classification counts (PDF-001)."""
    from PIL import Image as PILImage

    pdf_file = tmp_path / "scanned_like.pdf"
    img = PILImage.new("RGB", (400, 400), color="white")
    img.save(tmp_path / "page.png")
    # Blank pages with no text classify as scanned
    create_minimal_pdf(pdf_file)
    cmd = json.dumps({"command": "inspect", "file_path": str(pdf_file)})
    in_buf = io.StringIO(f"{cmd}\n")
    out_buf = io.StringIO()
    runner = SidecarRunner(in_stream=in_buf, out_stream=out_buf)
    runner.run_loop()
    out_lines = [json.loads(line) for line in out_buf.getvalue().strip().split("\n") if line.strip()]
    event = out_lines[0]
    summary = event.get("classification_summary", {})
    assert sum(summary.values()) == 2
    assert "scanned" in summary


def test_sidecar_convert_with_progress_and_checkpoint(tmp_path: Path):
    """Verify convert command emits real-time progress and checkpoint events (UI-002, UI-003)."""
    docx_file = tmp_path / "sample.docx"
    create_sample_docx(docx_file)
    out_pdf = tmp_path / "converted.pdf"

    cmd = json.dumps({
        "command": "convert",
        "file_path": str(docx_file),
        "output_path": str(out_pdf),
        "preset": "Large",
        "paper_size": "A4",
        "export_format": "pdf",
    })

    in_buf = io.StringIO(f"{cmd}\n")
    out_buf = io.StringIO()

    runner = SidecarRunner(in_stream=in_buf, out_stream=out_buf)
    runner.run_loop()

    out_lines = [json.loads(line) for line in out_buf.getvalue().strip().split("\n") if line.strip()]
    event_types = [ev["type"] for ev in out_lines]

    # Must contain progress and success
    assert EventType.PROGRESS.value in event_types
    assert EventType.SUCCESS.value in event_types

    # Check ProgressEvent contents (UI-002: meaningful human-readable state)
    progress_events = [ev for ev in out_lines if ev["type"] == EventType.PROGRESS.value]
    assert len(progress_events) >= 1
    p_ev = progress_events[0]
    assert "Importing Word document" in p_ev["message"] or "Extracting" in p_ev["message"]

    # Check SuccessEvent
    success_ev = [ev for ev in out_lines if ev["type"] == EventType.SUCCESS.value][0]
    assert success_ev["format"] == "pdf"
    assert out_pdf.exists()


def test_sidecar_export_reuses_built_document(tmp_path: Path):
    """Export must re-render the retained DocumentIR without re-importing (OUT-002, OUT-010)."""
    docx_file = tmp_path / "export_sample.docx"
    create_sample_docx(docx_file)
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"

    runner = SidecarRunner(in_stream=io.StringIO(), out_stream=io.StringIO())
    job_id = "job_export"

    out_buf = io.StringIO()
    runner.out_stream = out_buf
    runner.execute_command_str(json.dumps({
        "command": "convert",
        "id": job_id,
        "file_path": str(docx_file),
        "output_path": str(first_pdf),
        "export_format": "pdf",
        "preset": "Large",
    }))
    assert first_pdf.exists()
    assert job_id in runner._ir_stores

    # Re-importing on export would be a regression; make it explode if attempted.
    def explode(*args, **kwargs):
        raise AssertionError("export must not re-import the document")

    runner._orchestrator.docx_importer.import_document = explode

    export_buf = io.StringIO()
    runner.out_stream = export_buf
    runner.execute_command_str(json.dumps({
        "command": "export",
        "id": job_id,
        "job_id": job_id,
        "output_path": str(second_pdf),
        "export_format": "pdf",
        "preset": "Extra Large",
        "paper_size": "A3",
    }))

    lines = [json.loads(l) for l in export_buf.getvalue().strip().split("\n") if l.strip()]
    success = [l for l in lines if l.get("type") == EventType.SUCCESS.value]
    assert success, "export must emit a success event"
    assert success[0]["format"] == "pdf"
    assert second_pdf.exists()

    # A3 requested on the re-export must be honored (OUT-007/008).
    w, h = pdfium.PdfDocument(second_pdf)[0].get_size()
    assert round(w) == 842 and round(h) == 1191


def test_sidecar_export_without_document_reports_no_ir(tmp_path: Path):
    """Exporting before any conversion must fail with a clear, recoverable code."""
    runner = SidecarRunner(in_stream=io.StringIO(), out_stream=io.StringIO())
    out_buf = io.StringIO()
    runner.out_stream = out_buf

    runner.execute_command_str(json.dumps({
        "command": "export",
        "job_id": "never-converted",
        "output_path": str(tmp_path / "nope.pdf"),
    }))

    lines = [json.loads(l) for l in out_buf.getvalue().strip().split("\n") if l.strip()]
    assert len(lines) == 1
    assert lines[0]["type"] == EventType.ERROR.value
    assert lines[0]["code"] == "NO_IR"


def test_sidecar_review_data_and_retry(tmp_path: Path):
    """Verify review data query and per-page retry flow (UI-004, UI-005)."""
    runner = SidecarRunner(in_stream=io.StringIO(), out_stream=io.StringIO())
    job_id = "test_job_1"

    # Simulate a flagged page stored during conversion
    from openlargeprint.sidecar.protocol import FlaggedPageReview
    runner._review_stores[job_id] = [
        FlaggedPageReview(
            page_number=3,
            reason="Complex multi-column table required layout review",
            converted_text="| Item | Value |\n| --- | --- |\n| A | 1 |",
            confidence=0.72,
        )
    ]

    # 1. Query review data (UI-004)
    out_buf = io.StringIO()
    runner.out_stream = out_buf
    runner.execute_command_str(json.dumps({"command": "get_review_data", "job_id": job_id}))

    lines = [json.loads(l) for l in out_buf.getvalue().strip().split("\n") if l.strip()]
    assert len(lines) == 1
    rev_ev = lines[0]
    assert rev_ev["type"] == EventType.REVIEW_DATA.value
    assert rev_ev["total_flagged"] == 1
    assert "1 pages may need review" in rev_ev["summary_message"]
    assert rev_ev["flagged_pages"][0]["page_number"] == 3

    # 2. Retry flagged page with Maximum Accuracy (UI-004)
    out_buf_retry = io.StringIO()
    runner.out_stream = out_buf_retry
    runner.execute_command_str(json.dumps({
        "command": "retry_page",
        "job_id": job_id,
        "page_number": 3,
        "routing_mode": "maximum_accuracy",
    }))

    retry_lines = [json.loads(l) for l in out_buf_retry.getvalue().strip().split("\n") if l.strip()]
    assert len(retry_lines) == 1
    retry_ev = retry_lines[0]
    assert retry_ev["code"] == "FILE_NOT_FOUND"
    assert runner._review_stores[job_id][0].confidence == 0.72


def test_sidecar_plain_language_error_handling():
    """Verify technical exceptions are translated to plain-language error events (UI-005)."""
    # Request inspection on non-existent file
    cmd = json.dumps({"command": "inspect", "file_path": "/path/to/completely_missing_doc.pdf"})
    in_buf = io.StringIO(f"{cmd}\n")
    out_buf = io.StringIO()

    runner = SidecarRunner(in_stream=in_buf, out_stream=out_buf)
    runner.run_loop()

    lines = [json.loads(l) for l in out_buf.getvalue().strip().split("\n") if l.strip()]
    assert len(lines) == 1
    err_ev = lines[0]
    assert err_ev["type"] == EventType.ERROR.value
    assert err_ev["code"] == "FILE_NOT_FOUND"
    # Plain language assertion (UI-005)
    assert "could not be found" in err_ev["message"]
    # Ensure raw Python traceback is NOT dumped in message
    assert "Traceback" not in err_ev["message"]


def test_sidecar_invalid_json():
    """Verify malformed JSON emits an informative ErrorEvent."""
    in_buf = io.StringIO("This is not JSON at all\n")
    out_buf = io.StringIO()

    runner = SidecarRunner(in_stream=in_buf, out_stream=out_buf)
    runner.run_loop()

    lines = [json.loads(l) for l in out_buf.getvalue().strip().split("\n") if l.strip()]
    assert len(lines) == 1
    assert lines[0]["type"] == EventType.ERROR.value
    assert lines[0]["code"] == "INVALID_JSON"


def test_sidecar_unknown_command():
    """Verify unknown command name emits UNKNOWN_COMMAND error."""
    in_buf = io.StringIO('{"command": "nonexistent_op", "id": "cmd123"}\n\n')
    out_buf = io.StringIO()

    runner = SidecarRunner(in_stream=in_buf, out_stream=out_buf)
    runner.run_loop()

    lines = [json.loads(l) for l in out_buf.getvalue().strip().split("\n") if l.strip()]
    assert len(lines) == 1
    assert lines[0]["type"] == EventType.ERROR.value
    assert lines[0]["code"] == "UNKNOWN_COMMAND"
    assert lines[0]["job_id"] == "cmd123"


def test_sidecar_error_mappings():
    """Verify all technical exceptions map to plain language."""
    runner = SidecarRunner(in_stream=io.StringIO(), out_stream=io.StringIO())

    test_cases = [
        (ValueError("File format not recognized: xyz"), "UNSUPPORTED_FORMAT"),
        (ValueError("File exceeds maximum allowed size (500 MB)"), "FILE_TOO_LARGE"),
        (PermissionError("Access denied"), "PERMISSION_DENIED"),
        (TimeoutError("Engine took too long"), "TIMEOUT"),
        (RuntimeError("Unknown crash"), "CONVERSION_ERROR"),
    ]

    for exc, expected_code in test_cases:
        out_buf = io.StringIO()
        runner.out_stream = out_buf
        runner._handle_error(exc, job_id="job_err")
        lines = [json.loads(l) for l in out_buf.getvalue().strip().split("\n") if l.strip()]
        assert len(lines) == 1
        assert lines[0]["code"] == expected_code


def test_sidecar_cancellation(tmp_path: Path):
    """Verify cancel command stops conversion and emits CancelledEvent (UI-002)."""
    docx_file = tmp_path / "cancel_test.docx"
    create_sample_docx(docx_file)
    out_pdf = tmp_path / "cancel_out.pdf"

    runner = SidecarRunner(in_stream=io.StringIO(), out_stream=io.StringIO())
    job_id = "job_to_cancel"

    # Pre-set cancel flag
    runner._handle_cancel({"job_id": job_id})

    out_buf = io.StringIO()
    runner.out_stream = out_buf

    cmd = {
        "command": "convert",
        "id": job_id,
        "file_path": str(docx_file),
        "output_path": str(out_pdf),
    }
    runner.execute_command_str(json.dumps(cmd))

    lines = [json.loads(l) for l in out_buf.getvalue().strip().split("\n") if l.strip()]
    cancelled_events = [l for l in lines if l.get("type") == EventType.CANCELLED.value]
    assert len(cancelled_events) == 1
    assert cancelled_events[0]["job_id"] == job_id


def test_sidecar_cli_entrypoint():
    """Verify `openlargeprint sidecar` CLI sub-command executes JSON-Lines loop."""
    import subprocess
    import sys
    cmd = [sys.executable, "-m", "openlargeprint.cli", "sidecar"]
    res = subprocess.run(
        cmd,
        input='{"command": "health"}\n',
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [json.loads(l) for l in res.stdout.strip().split("\n") if l.strip()]
    assert len(lines) == 1
    assert lines[0]["type"] == EventType.HEALTH.value
    assert lines[0]["status"] == "ready"



def test_export_applies_review_edits_and_rejects_invalid_targets(tmp_path: Path):
    source = tmp_path / "source.docx"
    create_sample_docx(source)
    runner = SidecarRunner(in_stream=io.StringIO(), out_stream=io.StringIO())
    runner.execute_command_str(json.dumps({
        "command": "convert", "id": "edit_job", "file_path": str(source),
        "output_path": str(tmp_path / "first.pdf"), "export_format": "pdf",
    }))
    document = runner._ir_stores["edit_job"]
    block = next(block for block in document.blocks if block.text and block.type.value == "paragraph")
    original = source.read_bytes()
    command = {"command": "export", "id": "edit_job", "job_id": "edit_job",
               "output_path": str(tmp_path / "edited.html"), "export_format": "html",
               "text_edits": {block.id: "A reviewed correction survives export."}}
    runner.execute_command_str(json.dumps(command))
    assert "A reviewed correction survives export." in (tmp_path / "edited.html").read_text(encoding="utf-8")
    for changes in [{"output_path": str(source)}, {"text_edits": {"missing": "replacement"}},
                    {"export_format": "invalid"}, {"text_edits": {block.id: ["invalid"]}}]:
        runner.out_stream = io.StringIO()
        runner.execute_command_str(json.dumps(command | changes))
        events = [json.loads(line) for line in runner.out_stream.getvalue().splitlines()]
        assert any(event.get("type") == "error" for event in events)
        assert source.read_bytes() == original
