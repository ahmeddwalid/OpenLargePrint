"""Image recovery when the embedded copy cannot be decoded (IMG-001).

pikepdf delegates some codecs to external helpers (JBIG2 needs jbig2dec) and
raises DependencyError when they are missing, while pdfium carries its own
decoders. Real scanned books hit this: a page whose scan is JBIG2 loses its
images even though the engine that renders the page can read them.
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from openlargeprint.importers.pdf import images


def _one_pixel_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (120, 30, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


class _FailingImage:
    """Stands in for a pikepdf image whose codec needs a missing helper."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def as_pil_image(self):
        raise pikepdf.DependencyError("jbig2dec - not installed or not found")


class _StubPikePage:
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def get_images(self):
        return {name: object() for name in self._names}


class _StubPdfiumImage:
    def __init__(self, size: tuple[int, int], payload: bytes) -> None:
        self._size = size
        self._payload = payload
        self.extract_calls = 0

    def get_px_size(self) -> tuple[int, int]:
        return self._size

    def extract(self, fileobj) -> None:
        self.extract_calls += 1
        fileobj.write(self._payload)


class _StubPdfiumPage:
    def __init__(self, objects: list[_StubPdfiumImage]) -> None:
        self._objects = objects

    def get_objects(self, filter=None):
        return list(self._objects)


def _use_failing_image(monkeypatch, width: int, height: int) -> None:
    failing = _FailingImage(width, height)
    monkeypatch.setattr(images, "_coerce_pdf_image", lambda value: failing)


def test_images_undecodable_by_pikepdf_are_recovered_via_pdfium(tmp_path: Path, monkeypatch) -> None:
    _use_failing_image(monkeypatch, 1000, 800)
    stub_image = _StubPdfiumImage((1000, 800), _one_pixel_png())
    warnings: list[str] = []

    assets = images.extract_lossless_images_for_page(
        _StubPikePage(["fzImg1"]), 1, tmp_path,
        on_warning=warnings.append,
        pdfium_page=_StubPdfiumPage([stub_image]),
    )

    assert len(assets) == 1
    assert Path(assets[0].file_path).exists()
    assert assets[0].mime_type == "image/png"
    assert stub_image.extract_calls == 1
    assert any("DependencyError" in w for w in warnings), warnings
    assert any("re-decoded" in w for w in warnings), warnings


def test_recovery_converts_the_decoded_copy_to_png(tmp_path: Path, monkeypatch) -> None:
    """pdfium writes an image in its stored format (JP2, JBIG2); assets are PNG."""
    _use_failing_image(monkeypatch, 10, 10)
    jp2_payload = io.BytesIO()
    Image.new("RGB", (10, 10), (10, 90, 200)).save(jp2_payload, format="JPEG2000")
    stub_image = _StubPdfiumImage((10, 10), jp2_payload.getvalue())

    assets = images.extract_lossless_images_for_page(
        _StubPikePage(["fzImg1"]), 1, tmp_path,
        pdfium_page=_StubPdfiumPage([stub_image]),
    )

    assert len(assets) == 1
    with Image.open(assets[0].file_path) as recovered:
        assert recovered.format == "PNG"
        assert recovered.size == (10, 10)


def test_recovery_skips_images_that_decoded_losslessly(tmp_path: Path, monkeypatch) -> None:
    """Only the images that failed are recovered: no duplicated figures."""
    _use_failing_image(monkeypatch, 1000, 800)
    matching = _StubPdfiumImage((1000, 800), _one_pixel_png())
    other = _StubPdfiumImage((640, 480), _one_pixel_png())

    assets = images.extract_lossless_images_for_page(
        _StubPikePage(["fzImg1"]), 1, tmp_path,
        pdfium_page=_StubPdfiumPage([other, matching]),
    )

    assert len(assets) == 1
    assert other.extract_calls == 0
    assert matching.extract_calls == 1


def test_without_a_pdfium_page_the_failure_is_reported_not_hidden(tmp_path: Path, monkeypatch) -> None:
    _use_failing_image(monkeypatch, 1000, 800)
    warnings: list[str] = []

    assets = images.extract_lossless_images_for_page(
        _StubPikePage(["fzImg1"]), 1, tmp_path, on_warning=warnings.append
    )

    assert assets == []
    assert any("DependencyError" in w for w in warnings), warnings


def test_recovery_failure_is_reported(tmp_path: Path, monkeypatch) -> None:
    """If even pdfium cannot produce the image, say so instead of dropping it."""
    _use_failing_image(monkeypatch, 1000, 800)

    class _BrokenPdfiumImage(_StubPdfiumImage):
        def extract(self, fileobj) -> None:
            raise ValueError("page object is gone")

    warnings: list[str] = []
    assets = images.extract_lossless_images_for_page(
        _StubPikePage(["fzImg1"]), 1, tmp_path,
        on_warning=warnings.append,
        pdfium_page=_StubPdfiumPage([_BrokenPdfiumImage((1000, 800), b"")]),
    )

    assert assets == []
    assert any("could not be recovered" in w for w in warnings), warnings
