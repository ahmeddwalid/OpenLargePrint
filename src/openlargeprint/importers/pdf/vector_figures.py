"""Region-crop fallback for non-embeddable vector figures (IMG-002, DESIGN.md §5).

When a page contains vector artwork but no recoverable embedded raster, the
figure would otherwise vanish from the reflowed output. This module renders the
source region at a suitable resolution so the artwork is preserved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from openlargeprint.ir.models import ImageAsset
from openlargeprint.security.validator import bounded_pdf_scale

# Conservative thresholds so text rules / table hairlines are not mistaken for figures.
_MIN_PATH_OBJECTS = 1
_MIN_REGION_AREA_RATIO = 0.04
_MIN_REGION_SIDE_PT = 30.0
_RENDER_DPI = 200.0


def extract_vector_figure_region(
    page: pdfium.PdfPage,
    page_num: int,
    assets_dir: Path,
    page_width: float,
    page_height: float,
    occupied_bboxes: Optional[List[Tuple[float, float, float, float]]] = None,
    on_warning: Optional[Callable[[str], None]] = None,
) -> Optional[ImageAsset]:
    """Render the bounding region of a page's vector artwork as a figure (IMG-002).

    Returns ``None`` (and never raises) when the page has no plausible vector
    figure. ``occupied_bboxes`` lets the caller suppress regions already covered
    by a detected table so table rules are not duplicated as a figure.
    """

    def _warn(message: str) -> None:
        if on_warning is not None:
            on_warning(message)

    try:
        path_objects = list(page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_PATH]))
    except Exception as exc:
        _warn(f"Vector figure scan failed on page {page_num}: {type(exc).__name__}")
        return None

    if len(path_objects) < _MIN_PATH_OBJECTS:
        return None

    bounds: List[Tuple[float, float, float, float]] = []
    for obj in path_objects:
        try:
            left, bottom, right, top = obj.get_bounds()
        except Exception:
            continue
        if right - left <= 0 or top - bottom <= 0:
            continue
        bounds.append((float(left), float(bottom), float(right), float(top)))

    if len(bounds) < _MIN_PATH_OBJECTS:
        return None

    x0 = min(b[0] for b in bounds)
    y0 = min(b[1] for b in bounds)
    x1 = max(b[2] for b in bounds)
    y1 = max(b[3] for b in bounds)

    region_w = x1 - x0
    region_h = y1 - y0
    if region_w < _MIN_REGION_SIDE_PT or region_h < _MIN_REGION_SIDE_PT:
        return None

    page_area = max(1.0, page_width * page_height)
    if (region_w * region_h) / page_area < _MIN_REGION_AREA_RATIO:
        return None

    # Skip regions that a detected table already covers (TBL-001 / IMG-002).
    for ob in occupied_bboxes or []:
        ox0, oy0, ox1, oy1 = ob
        inter_w = max(0.0, min(x1, ox1) - max(x0, ox0))
        inter_h = max(0.0, min(y1, oy1) - max(y0, oy0))
        if (inter_w * inter_h) / max(1.0, region_w * region_h) > 0.6:
            return None

    try:
        scale = bounded_pdf_scale(page_width, page_height, _RENDER_DPI)
        # ``crop`` is expressed as edge margins (left, bottom, right, top) cut from
        # the page, not absolute coordinates.
        pad = 6.0
        left = max(0.0, x0 - pad)
        bottom = max(0.0, y0 - pad)
        right = max(0.0, page_width - min(page_width, x1 + pad))
        top = max(0.0, page_height - min(page_height, y1 + pad))
        bitmap = page.render(scale=scale, crop=(left, bottom, right, top))
        pil_img = bitmap.to_pil()
        asset_id = f"p{page_num}_vector_fig"
        out_path = assets_dir / f"{asset_id}.png"
        try:
            pil_img.save(out_path, format="PNG")
        finally:
            bitmap.close()
        return ImageAsset(
            asset_id=asset_id,
            file_path=str(out_path),
            mime_type="image/png",
            width=pil_img.width,
            height=pil_img.height,
            alt_text=f"Figure rendered from page {page_num}",
        )
    except Exception as exc:
        _warn(f"Could not render vector figure on page {page_num}: {type(exc).__name__}")
        return None
