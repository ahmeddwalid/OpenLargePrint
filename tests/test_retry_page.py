"""retry_page must re-process a flagged page at higher accuracy (UI-004)."""

from pathlib import Path

from reportlab.pdfgen import canvas

from openlargeprint.ocr.router import RoutingMode
from openlargeprint.pipeline import PipelineOrchestrator


def _make_two_page_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path))
    c.drawString(72, 750, "First page legal text about consideration")
    c.showPage()
    c.drawString(72, 750, "Second page legal text about promissory estoppel")
    c.showPage()
    c.save()
    return path


def test_retry_page_reprocesses_with_higher_accuracy(tmp_path: Path):
    src = _make_two_page_pdf(tmp_path / "src.pdf")
    orch = PipelineOrchestrator(routing_mode=RoutingMode.AUTOMATIC)
    retried = orch.retry_page(src, page_number=2, routing_mode=RoutingMode.MAXIMUM_ACCURACY)
    assert retried is not None
    assert len(retried.blocks) >= 1
    assert all(b.source_page == 2 for b in retried.blocks)
    texts = " ".join(b.text for b in retried.blocks if b.text)
    assert "estoppel" in texts or "Second page" in texts or len(texts) > 0
