"""Shared test helpers.

Word documents written by the exporter carry their formatting in named styles
(Heading 1, List Item, Footnote Text...) rather than on every run, the way a
person editing in Word would expect. These helpers read the size, weight and
spacing a reader actually sees, walking from the run to its paragraph style and
up the style's base styles.
"""

from __future__ import annotations

import pytest

from openlargeprint.models import model_manager


def _style_chain(paragraph):
    style = paragraph.style
    while style is not None:
        yield style
        style = style.base_style


def effective_size(paragraph, run=None) -> float:
    """Text size in points for ``run`` (default: the paragraph's first run)."""
    run = run if run is not None else (paragraph.runs[0] if paragraph.runs else None)
    if run is not None and run.font.size is not None:
        return run.font.size.pt
    for style in _style_chain(paragraph):
        if style.font.size is not None:
            return style.font.size.pt
    raise AssertionError("no text size set on the run or its styles")


def effective_bold(paragraph, run=None) -> bool:
    run = run if run is not None else (paragraph.runs[0] if paragraph.runs else None)
    if run is not None and run.font.bold is not None:
        return bool(run.font.bold)
    for style in _style_chain(paragraph):
        if style.font.bold is not None:
            return bool(style.font.bold)
    return False


def effective_line_spacing(paragraph):
    if paragraph.paragraph_format.line_spacing is not None:
        return paragraph.paragraph_format.line_spacing
    for style in _style_chain(paragraph):
        if style.paragraph_format.line_spacing is not None:
            return style.paragraph_format.line_spacing
    return None


def layout_model_available() -> bool:
    try:
        model_manager.get_model_path("pp_doc_layoutv2", verify=False)
        return True
    except Exception:
        return False


# Behaviour that only the bundled layout model can provide (unruled tables,
# figure/caption pairing). Releases and CI fetch the model first; a bare
# checkout without it still runs every other test.
requires_layout_model = pytest.mark.skipif(
    not layout_model_available(),
    reason="layout model not installed (run: python scripts/fetch_models.py)",
)
