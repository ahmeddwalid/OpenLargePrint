"""Tests for cross-platform font resolution and bundled Arabic font discovery (LANG-001, LANG-002, OUT-003)."""

from pathlib import Path
from unittest.mock import patch

from openlargeprint.exporters.fonts import (
    _bundled_font_dirs,
    _candidate_font_dirs,
    css_font_stack,
    ensure_arabic_font,
    find_font_file,
    resolve_reportlab_family,
)


def test_bundled_font_dirs_finds_ui_public_fonts():
    """Verify bundled fonts directory is located relative to repository root."""
    dirs = _bundled_font_dirs()
    assert len(dirs) >= 1
    found_noto = any((d / "NotoSansArabic.ttf").exists() for d in dirs)
    assert found_noto, f"NotoSansArabic.ttf not found in bundled font directories: {dirs}"


def test_candidate_font_dirs_includes_bundled():
    """Candidate font search directories must include the bundled project fonts."""
    dirs = _candidate_font_dirs()
    assert any((d / "NotoSansArabic.ttf").exists() for d in dirs)


def test_ensure_arabic_font_finds_bundled_arabic():
    """ensure_arabic_font must register the bundled Arabic font, not fall back to Helvetica."""
    import openlargeprint.exporters.fonts as fonts_mod
    fonts_mod._arabic_font_name = None  # Reset cached name

    font_name = ensure_arabic_font()
    assert font_name == "OpenLargePrintArabic"


def test_ensure_arabic_font_succeeds_even_without_system_fonts(monkeypatch):
    """Even on a clean OS with zero host Arabic fonts, bundled font ensures Arabic support."""
    import openlargeprint.exporters.fonts as fonts_mod
    fonts_mod._arabic_font_name = None

    # Blank out system candidates
    monkeypatch.setattr(fonts_mod, "_ARABIC_CANDIDATES", ["/nonexistent/path/font.ttf"])

    font_name = ensure_arabic_font()
    assert font_name == "OpenLargePrintArabic"


def test_css_font_stack_formatting():
    """CSS font stack should format family with quotes and system fallbacks."""
    stack = css_font_stack("Source Sans 3", "Arial")
    assert '"Source Sans 3"' in stack
    assert '"Segoe UI"' in stack
    assert "sans-serif" in stack


def test_resolve_reportlab_family_unknown_falls_back():
    """Unknown families should safely fall back to standard Helvetica variants."""
    resolved = resolve_reportlab_family("CompletelyNonExistentFamily12345")
    assert resolved["normal"] == "Helvetica"
    assert resolved["bold"] == "Helvetica-Bold"
