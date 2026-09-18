"""Non-contiguous page selection slicing (OUT-010)."""

from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    PageClassification,
    PageMetadata,
)


def _make_doc(n_pages=5) -> DocumentIR:
    pages = [
        PageMetadata(
            page_number=i,
            width=595,
            height=842,
            classification=PageClassification.NATIVE,
        )
        for i in range(1, n_pages + 1)
    ]
    blocks: list[Block] = []
    for i in range(1, n_pages + 1):
        blocks.append(
            Block(id=f"p{i}_m", type=BlockType.PAGE_MARKER, source_page=i, page_marker=i)
        )
        blocks.append(
            Block(id=f"p{i}_b1", type=BlockType.PARAGRAPH, text=f"Page {i} text", source_page=i)
        )
    return DocumentIR(
        metadata=DocumentMetadata(title="t", page_count=n_pages),
        pages=pages,
        blocks=blocks,
    )


def test_slice_non_contiguous_pages():
    doc = _make_doc(5)
    sliced = doc.slice_by_source_pages_set({1, 3, 5})
    pages = {b.page_marker for b in sliced.blocks if b.type == BlockType.PAGE_MARKER}
    assert pages == {1, 3, 5}
    assert {b.source_page for b in sliced.blocks} == {1, 3, 5}
    assert len(sliced.pages) == 3


def test_slice_set_invalid_raises():
    doc = _make_doc(5)
    import pytest

    with pytest.raises(ValueError, match="Invalid page selection"):
        doc.slice_by_source_pages_set(set())
    with pytest.raises(ValueError, match="Invalid page selection"):
        doc.slice_by_source_pages_set({0, 2})


def test_orchestrator_accepts_list_page_range(tmp_path):
    """Orchestrator.convert must accept a list of pages (OUT-010)."""
    from reportlab.pdfgen import canvas
    from openlargeprint.pipeline import PipelineOrchestrator

    src = tmp_path / "src.pdf"
    c = canvas.Canvas(str(src))
    for i in range(3):
        c.drawString(72, 750, f"Page content {i + 1}")
        c.showPage()
    c.save()
    out = tmp_path / "out.pdf"
    orch = PipelineOrchestrator()
    res = orch.convert(src, out, export_format="pdf", page_range=[1, 3])
    assert res.success
    assert {b.source_page for b in res.document_ir.blocks} <= {1, 3}


def test_orchestrator_accepts_string_page_range(tmp_path):
    """Orchestrator.convert must accept a string page range (OUT-010)."""
    from reportlab.pdfgen import canvas
    from openlargeprint.pipeline import PipelineOrchestrator

    src = tmp_path / "src_str.pdf"
    c = canvas.Canvas(str(src))
    for i in range(5):
        c.drawString(72, 750, f"Page content {i + 1}")
        c.showPage()
    c.save()

    out = tmp_path / "out_str.pdf"
    orch = PipelineOrchestrator()
    res = orch.convert(src, out, export_format="pdf", page_range="1-2, 4")
    assert res.success
    source_pages = {b.source_page for b in res.document_ir.blocks if b.source_page is not None}
    assert source_pages == {1, 2, 4}

