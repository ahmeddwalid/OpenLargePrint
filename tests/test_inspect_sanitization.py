"""inspect() must sanitize active content before parsing (SEC-002)."""

from pathlib import Path

import pikepdf

from openlargeprint.pipeline import PipelineOrchestrator


def _make_js_pdf(path: Path) -> Path:
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(595, 842))
    js_dict = pikepdf.Dictionary({
        "/S": pikepdf.Name("/JavaScript"),
        "/JS": pikepdf.String("app.alert('malicious script executed');"),
    })
    pdf.Root["/OpenAction"] = js_dict
    pdf.Root["/Names"] = pikepdf.Dictionary({
        "/JavaScript": pikepdf.Dictionary({}),
    })
    pdf.save(path)
    pdf.close()
    return path


def test_inspect_sanitizes_before_parsing(tmp_path: Path, monkeypatch):
    """inspect() must route input through sanitize_document (SEC-002)."""
    import openlargeprint.pipeline.orchestrator as orch_mod

    calls: list[str] = []
    real_sanitize = orch_mod.sanitize_document

    def tracking_sanitize(input_path, workspace_dir):
        calls.append(str(input_path))
        return real_sanitize(input_path, workspace_dir)

    monkeypatch.setattr(orch_mod, "sanitize_document", tracking_sanitize)
    js_pdf = _make_js_pdf(tmp_path / "with_js.pdf")
    orchestrator = PipelineOrchestrator()
    doc_ir = orchestrator.inspect(js_pdf)
    assert doc_ir is not None
    assert calls, "inspect() never called sanitize_document (SEC-002)"


def test_inspect_strips_pdf_javascript(tmp_path: Path):
    """A PDF with embedded JavaScript must be sanitized during inspect()."""
    from openlargeprint.security import sanitize_pdf

    js_pdf = _make_js_pdf(tmp_path / "with_js.pdf")
    orchestrator = PipelineOrchestrator()
    doc_ir = orchestrator.inspect(js_pdf)
    assert doc_ir is not None
    clean_path = tmp_path / "sanitized.pdf"
    _, stripped = sanitize_pdf(js_pdf, clean_path)
    assert len(stripped) >= 1
    assert any("OpenAction" in s or "JavaScript" in s for s in stripped)
    sanitized_pdf = pikepdf.open(clean_path)
    assert "/OpenAction" not in sanitized_pdf.Root
    sanitized_pdf.close()
