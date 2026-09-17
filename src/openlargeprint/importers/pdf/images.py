"""Lossless embedded image extraction from PDF (IMG-001, IMG-003)."""

from __future__ import annotations

from pathlib import Path
from typing import List
import pikepdf
from openlargeprint.ir.models import ImageAsset
from openlargeprint.security.validator import validate_image_dimensions


def extract_lossless_images_for_page(
    pike_page: pikepdf.Page,
    page_num: int,
    assets_dir: Path,
) -> List[ImageAsset]:
    """Extract embedded images losslessly from a PDF page using pikepdf (IMG-001).
    
    Verifies dimensions bounds (SEC-003) and preserves original aspect ratio (IMG-003).
    """
    images: List[ImageAsset] = []

    try:
        page_images = pike_page.get_images()
    except Exception:
        return images

    for name, raw_img in page_images.items():
        try:
            pdf_img = pikepdf.PdfImage(raw_img)
            width = int(pdf_img.width)
            height = int(pdf_img.height)

            # Enforce dimension safety bounds (SEC-003)
            validate_image_dimensions(width, height)

            safe_name = name.lstrip("/").replace(" ", "_")
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
        except Exception:
            # If an individual image extraction fails or exceeds bounds, continue
            # preserving other content rather than aborting the page
            continue

    return images
