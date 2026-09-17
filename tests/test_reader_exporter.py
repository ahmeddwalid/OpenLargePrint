"""Tests for Semantic HTML Reader exporter (OUT-002, A11Y-001..004, SEC-009)."""

from pathlib import Path
import re
import pytest

from openlargeprint.exporters import ExportOptions, PresetName, ReaderExporter
from openlargeprint.ir.models import (
    Block,
    BlockType,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    PageClassification,
    PageMetadata,
)


def create_reader_test_ir() -> DocumentIR:
    metadata = DocumentMetadata(title="Civil Rights & Judicial Equality", page_count=2)
    pages = [
        PageMetadata(page_number=1, width=595, height=842, classification=PageClassification.NATIVE),
        PageMetadata(page_number=2, width=595, height=842, classification=PageClassification.NATIVE),
    ]
    blocks = [
        Block(id="p1_m", type=BlockType.PAGE_MARKER, source_page=1, page_marker=1),
        Block(id="p1_h1", type=BlockType.HEADING, text="Equal Protection Under Law", level=1, source_page=1),
        Block(id="p1_p1", type=BlockType.PARAGRAPH, text="No State shall deny to any person equal protection.", source_page=1),
        Block(id="p1_q1", type=BlockType.QUOTE, text="Separate educational facilities are inherently unequal.", source_page=1),
        Block(id="p2_m", type=BlockType.PAGE_MARKER, source_page=2, page_marker=2),
        Block(id="p2_p1", type=BlockType.PARAGRAPH, text="Judicial scrutiny must remain exacting.", source_page=2),
    ]
    return DocumentIR(metadata=metadata, pages=pages, blocks=blocks)


def test_reader_export_accessible_html(tmp_path: Path):
    """Verify Reader exports accessible HTML with 44px buttons, themes, and semantic structure."""
    doc_ir = create_reader_test_ir()
    out_html = tmp_path / "reader.html"

    exporter = ReaderExporter()
    options = ExportOptions(preset=PresetName.LARGE)
    exporter.export(doc_ir, out_html, options)

    assert out_html.exists()
    content = out_html.read_text(encoding="utf-8")

    # 1. Semantic tags
    assert "<h1" in content
    assert "Equal Protection Under Law" in content
    assert "<blockquote>" in content
    assert "— Original Page 1 —" in content
    assert 'id="orig-page-1"' in content
    assert 'id="orig-page-2"' in content

    # 2. Touch target accessibility: min 44px (A11Y-001)
    assert "min-width: 44px" in content
    assert "min-height: 44px" in content

    # 3. Themes supported (A11Y-004)
    assert '[data-theme="dark"]' in content
    assert '[data-theme="sepia"]' in content

    # 4. Instant re-styling controls present (OUT-002)
    assert 'id="btn-size-dec"' in content
    assert 'id="btn-size-inc"' in content
    assert 'id="theme-dark"' in content
    assert 'id="btn-print"' in content

    # 5. Zero external network resources (SEC-009)
    # Check that no external script or stylesheet URLs are linked
    external_scripts = re.findall(r'<script[^>]+src=["\'](http[s]?://[^"\']+)["\']', content)
    external_links = re.findall(r'<link[^>]+href=["\'](http[s]?://[^"\']+)["\']', content)
    assert len(external_scripts) == 0
    assert len(external_links) == 0
