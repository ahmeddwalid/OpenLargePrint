"""Lossless embedded image extraction from PDF (IMG-001, IMG-003)."""

from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Callable, List, Optional, Tuple
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


def _recover_images_with_pdfium(
    pdfium_page,
    page_num: int,
    assets_dir: Path,
    failed_sizes: List[Tuple[int, int]],
    _warn: Callable[[str], None],
    existing_sizes: Optional[List[Tuple[int, int]]] = None,
) -> List[ImageAsset]:
    """Decode images pikepdf could not read, using pdfium's own decoders (IMG-001).

    pikepdf delegates some codecs to external helpers (JBIG2 needs jbig2dec) and
    raises DependencyError when a helper is missing, while pdfium carries its own
    decoders. Scanned books hit this often, and dropping those images silently
    would contradict IMG-001, so the page object is asked for the same image.

    The recovered asset is a decoded copy rather than the original encoded
    stream. That distinction is reported through ``on_warning`` instead of being
    substituted without a trace.
    """
    recovered: List[ImageAsset] = []
    if pdfium_page is None:
        return recovered

    known_sizes = set(existing_sizes or [])
    pending = list(failed_sizes)

    try:
        from pypdfium2 import raw as pdfium_c

        objects = list(pdfium_page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]))
    except Exception as exc:
        _warn(f"Page {page_num} images could not be re-read for recovery ({type(exc).__name__})")
        return recovered

    if not objects:
        return recovered

    for index, obj in enumerate(objects):
        try:
            px_size = obj.get_px_size()
            size: Tuple[int, int] = (int(px_size[0]), int(px_size[1]))
        except Exception:
            continue
        if size in known_sizes:
            # Decoded losslessly already: never add a second copy of the same figure.
            continue

        # If we have explicit pending failures, prioritize those; otherwise recover missing objects
        if pending and size not in pending:
            continue

        width, height = size
        try:
            validate_image_dimensions(width, height)  # SEC-003, checked before decoding
        except Exception as exc:
            _warn(f"Image on page {page_num} was not recovered ({type(exc).__name__})")
            continue

        asset_id = f"p{page_num}_recovered_{index}"
        out_path = assets_dir / f"{asset_id}.png"
        try:
            with open(out_path, "wb") as handle:
                obj.extract(handle)
            # pdfium writes the image in its stored format (JP2, PNG, ...) while the
            # pipeline expects PNG assets, so normalise the decoded copy.
            from PIL import Image

            with Image.open(out_path) as decoded:
                decoded.convert("RGB").save(out_path, format="PNG")
        except Exception as exc:
            if out_path.exists():
                out_path.unlink()
            _warn(f"Image on page {page_num} could not be recovered ({type(exc).__name__})")
            continue

        recovered.append(
            ImageAsset(
                asset_id=asset_id,
                file_path=str(out_path),
                mime_type="image/png",
                width=width,
                height=height,
                alt_text=f"Figure from page {page_num}",
            )
        )
        known_sizes.add(size)
        if size in pending:
            pending.remove(size)
        _warn(
            f"Image on page {page_num} was re-decoded because the embedded copy could not be read"
            " (the reflowed output carries the decoded copy)"
        )

    return recovered


def extract_lossless_images_for_page(
    pike_page: pikepdf.Page,
    page_num: int,
    assets_dir: Path,
    on_warning: Optional[Callable[[str], None]] = None,
    pdfium_page=None,
) -> List[ImageAsset]:
    """Extract embedded images losslessly from a PDF page using pikepdf (IMG-001).

    Uses the recursive ``get_images()`` API so images nested inside form
    XObjects are found. Verifies dimensions bounds (SEC-003), preserves the
    original aspect ratio (IMG-003), and reports every skipped image through
    ``on_warning`` instead of dropping it silently.

    ``pdfium_page`` is the matching page object from the rendering engine. It is
    used only to recover images whose codec pikepdf cannot decode on this
    machine, so passing it leaves the lossless path untouched.
    """

    def _warn(message: str) -> None:
        if on_warning is not None:
            on_warning(message)

    images: List[ImageAsset] = []
    failed_sizes: List[Tuple[int, int]] = []

    page_images = None
    try:
        get_images = getattr(pike_page, "get_images", None)
        if callable(get_images):
            page_images = get_images()
        else:
            page_images = getattr(pike_page, "images", None)
    except Exception as exc:
        _warn(f"Could not enumerate images on page {page_num}: {type(exc).__name__}")

    # Fallback to direct page Resources XObjects if get_images() found nothing
    if not page_images:
        try:
            res = getattr(pike_page, "Resources", None)
            if res and "/XObject" in res:
                direct_images = {}
                for k, v in res.XObject.items():
                    if getattr(v, "Subtype", None) == "/Image":
                        direct_images[k] = v
                if direct_images:
                    page_images = direct_images
        except Exception:
            pass

    if page_images:
        for name, raw_img in page_images.items():
            safe_name = hashlib.sha256(str(name).encode("utf-8")).hexdigest()[:16]
            width = 0
            height = 0
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
                if width > 0 and height > 0:
                    failed_sizes.append((width, height))

    existing_sizes = [(img.width, img.height) for img in images]
    images.extend(
        _recover_images_with_pdfium(
            pdfium_page,
            page_num,
            assets_dir,
            failed_sizes,
            _warn,
            existing_sizes=existing_sizes,
        )
    )

    return images
