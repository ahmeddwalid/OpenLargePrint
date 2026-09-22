"""Page-filling artwork is preserved only when explicitly requested (IMG-001, PDF-004)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from openlargeprint.ir.models import BlockType
from openlargeprint.pipeline import PipelineOrchestrator


def _build_native_page_with_full_page_image(path: Path) -> Path:
    """A text page whose background is a single full-page image (the textbook case)."""
    artwork = Image.new("RGB", (595, 842), (232, 226, 210))
    draw = ImageDraw.Draw(artwork)
    draw.rectangle([40, 40, 555, 400], fill=(196, 160, 120))
    draw.ellipse([120, 120, 420, 320], fill=(120, 150, 170))
    artwork_path = path.with_suffix(".png")
    artwork.save(artwork_path)

    sheet = canvas.Canvas(str(path), pagesize=A4)
    sheet.drawImage(str(artwork_path), 0, 0, width=A4[0], height=A4[1])
    sheet.drawString(72, 780, "Chapter 1: The page artwork is part of the document.")
    sheet.showPage()
    sheet.save()
    return path


def _image_blocks(result) -> int:
    return len([b for b in result.document_ir.blocks if b.type == BlockType.IMAGE])


def _omission_warnings(result) -> list[str]:
    return [w for w in result.warnings if "background image was omitted" in w]


def test_full_page_artwork_is_omitted_by_default(tmp_path: Path) -> None:
    """The default stays text-first: no page raster is carried into the output."""
    pdf = _build_native_page_with_full_page_image(tmp_path / "art.pdf")

    result = PipelineOrchestrator().convert(pdf, tmp_path / "out.pdf", export_format="pdf")

    assert _omission_warnings(result), result.warnings
    assert _image_blocks(result) == 0


def test_full_page_artwork_is_kept_when_requested(tmp_path: Path) -> None:
    """Opting in keeps the artwork, and stops reporting it as omitted."""
    pdf = _build_native_page_with_full_page_image(tmp_path / "art.pdf")

    result = PipelineOrchestrator(preserve_page_artwork=True).convert(
        pdf, tmp_path / "out.pdf", export_format="pdf"
    )

    assert not _omission_warnings(result), result.warnings
    assert _image_blocks(result) >= 1


def test_text_is_extracted_the_same_way_in_both_modes(tmp_path: Path) -> None:
    """The option changes artwork retention only: text extraction is untouched."""
    pdf = _build_native_page_with_full_page_image(tmp_path / "art.pdf")

    default = PipelineOrchestrator().convert(pdf, tmp_path / "a.pdf", export_format="pdf")
    preserving = PipelineOrchestrator(preserve_page_artwork=True).convert(
        pdf, tmp_path / "b.pdf", export_format="pdf"
    )

    def _text(result) -> str:
        return " ".join(b.text for b in result.document_ir.blocks if b.text)

    assert _text(default) == _text(preserving)
    assert "Chapter 1" in _text(preserving)

def test_cli_flag_reaches_the_pipeline(tmp_path: Path) -> None:
    """The advanced flag must survive argument parsing, not merely exist (UI-001)."""
    import subprocess
    import sys

    pdf = _build_native_page_with_full_page_image(tmp_path / "art.pdf")

    def _convert(*extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "openlargeprint.cli", "convert", str(pdf),
             "--output", str(tmp_path / "cli.pdf"), "--format", "pdf", *extra],
            capture_output=True, text=True,
        )

    default = _convert()
    preserving = _convert("--preserve-page-artwork")

    assert default.returncode == 0, default.stdout + default.stderr
    assert preserving.returncode == 0, preserving.stdout + preserving.stderr
    assert "background image was omitted" in default.stdout
    assert "background image was omitted" not in preserving.stdout
