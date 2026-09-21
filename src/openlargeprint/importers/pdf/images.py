"""Lossless embedded image extraction from PDF (IMG-001, IMG-003)."""

from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Callable, List, Optional
import pikepdf
from openlargeprint.ir.models import ImageAsset
from openlargeprint.security.validator import validate_image_dimensions


def _coerce_pdf_image(value):
    """Return a ``PdfImage`` from a pikepdf page-image value.

    Depending on pikepdf version, ``Page.get_images()`` yields either raw
    ``Object`` values or already-constructed ``PdfImage`` instances.
    """
    if isinstance(value, pikepdf.PdfImage):
        return value
    return pikepdf.PdfImage(value)


def extract_lossless_images_for_page(
    pike_page: pikepdf.Page,
    page_num: int,
    assets_dir: Path,
    on_warning: Optional[Callable[[str], None]] = None,
) -> List[ImageAsset]:
    """Extract embedded images losslessly from a PDF page using pikepdf (IMG-001).

    Uses the recursive ``get_images()`` API so images nested inside form
    XObjects are found. Verifies dimensions bounds (SEC-003), preserves the
    original aspect ratio (IMG-003), and reports every skipped image through
    ``on_warning`` instead of dropping it silently.
    """

    def _warn(message: str) -> None:
        if on_warning is not None:
            on_warning(message)

    images: List[ImageAsset] = []

    page_images = None
    try:
        get_images = getattr(pike_page, "get_images", None)
        if callable(get_images):
            page_images = get_images()
        else:
            page_images = getattr(pike_page, "images", None)
    except Exception as exc:
        _warn(f"Could not enumerate images on page {page_num}: {type(exc).__name__}")
        return images

    if not page_images:
        return images

    for name, raw_img in page_images.items():
        safe_name = hashlib.sha256(str(name).encode("utf-8")).hexdigest()[:16]
        try:
            pdf_img = _coerce_pdf_image(raw_img)
            width = int(pdf_img.width)
            height = int(pdf_img.height)

            # Enforce dimension safety bounds (SEC-003)
            validate_image_dimensions(width, height)

            asset_id = f"p{page_num}_{safe_name}"
            out_path = assets_dir / f"{asset_id}.png"

            # Convert to PIL image and save losslessly
            pil_img = pdf_img.as_pil_image()
            pil_img.save(out_path, format="PNG")

            images.append(
                ImageAsset(
                    asset_id=asset_id,
                    file_path=str(out_path),
                    mime_type="image/png",
                    width=width,
                    height=height,
                    alt_text=f"Figure from page {page_num}",
                )
            )
        except Exception as exc:
            # Preserve other content, but never lose the failure silently (IMG-001).
            _warn(f"Image on page {page_num} could not be extracted ({type(exc).__name__}); it may be missing from the output")

    return images
