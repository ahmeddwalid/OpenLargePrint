"""The Arabic corpus page must contain real Arabic text (QA-002, LANG-002, OCR-003).

The fixture drew its Arabic strings with PIL's default bitmap font, which has no
Arabic glyph coverage: the page came out as replacement boxes. Every Arabic
recognition number measured against that page was therefore meaningless, and the
case could not have ground truth attached to it.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageFont
import numpy as np

from openlargeprint.qa.corpus_builder import BenchmarkCorpusBuilder


def test_arabic_fixture_renders_with_the_bundled_arabic_font() -> None:
    builder = BenchmarkCorpusBuilder(output_dir=Path("scratch") / "arabic_fixture_probe")

    font = builder.arabic_font(28)

    assert isinstance(font, ImageFont.FreeTypeFont)
    assert str(font.path).endswith("NotoSansArabic.ttf"), str(font.path)


def test_arabic_fixture_writes_ground_truth_for_both_lines(tmp_path: Path) -> None:
    builder = BenchmarkCorpusBuilder(output_dir=tmp_path)

    page = builder.build_arabic_scan()

    ground_truth = page.with_suffix(".txt")
    assert ground_truth.exists(), "the Arabic page has no reference transcript, so CER stays unmeasured"
    text = ground_truth.read_text(encoding="utf-8")
    assert "عقد بيع ابتدائي وتنازل" in text
    assert "تم الاتفاق بين الطرفين على البنود والشروط المذكورة أدناه." in text

    mirrored = tmp_path / "ocr_ground_truth" / f"{page.stem}.txt"
    assert mirrored.exists()


def test_the_page_is_not_a_blank_or_boxed_render(tmp_path: Path) -> None:
    """Replacement boxes come out as uniform small blobs; real glyphs leave varied ink."""
    builder = BenchmarkCorpusBuilder(output_dir=tmp_path)
    builder.build_arabic_scan()

    grey = np.asarray(builder.render_arabic_page().convert("L"))
    ink_columns = int((grey[90:220, :] < 128).any(axis=0).sum())

    # Two Arabic lines drawn at real size cover far more horizontal ink than a
    # fallback-font render of the same strings would.
    assert ink_columns > 40, f"only {ink_columns} columns contain ink"
