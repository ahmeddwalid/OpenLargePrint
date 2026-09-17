"""PDF page classifier using cheap diagnostic signals (PDF-001, PDF-007)."""

from __future__ import annotations

from typing import Tuple
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from openlargeprint.ir.models import PageClassification, PageMetadata

REPLACEMENT_GLYPHS = {"\ufffd", "\u25a0", "\u25ae", "\u25af", "\u25fd", "\u25fe"}


def classify_pdf_page(page: pdfium.PdfPage, page_number: int) -> PageMetadata:
    """Classify a single PDF page into native, scanned, mixed, or broken-digital (PDF-001).
    
    Operates on cheap diagnostic signals (text presence, character sanity, raster coverage,
    rotation) without invoking expensive OCR models.
    """
    width, height = page.get_size()
    rotation = page.get_rotation()
    page_area = max(1.0, float(width * height))

    # 1. Native text inspection
    textpage = page.get_textpage()
    try:
        char_count = textpage.count_chars()
        text = textpage.get_text_range() if char_count > 0 else ""
    finally:
        textpage.close()

    # 2. Raster coverage calculation
    total_image_area = 0.0
    image_count = 0
    for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        try:
            l, b, r, t = obj.get_bounds()
            w = abs(r - l)
            h = abs(t - b)
            total_image_area += (w * h)
            image_count += 1
        except Exception:
            continue

    raster_coverage = min(1.0, total_image_area / page_area)

    # 3. Character plausibility (detecting broken-digital text layers)
    clean_text = text.strip()
    is_broken = False
    if char_count > 0 and len(text) > 0:
        replacement_count = sum(
            1
            for c in text
            if c in REPLACEMENT_GLYPHS
            or (0xE000 <= ord(c) <= 0xF8FF)  # Private Use Area (missing ToUnicode CMap)
            or (ord(c) < 32 and c not in "\n\r\t")
        )
        printable_count = sum(
            1 for c in text if (c.isprintable() or c in "\n\r\t") and c not in REPLACEMENT_GLYPHS
        )

        printable_ratio = printable_count / len(text)
        replacement_ratio = replacement_count / len(text)

        # Broken text layer check (e.g. garbled font encodings, missing ToUnicode CMap)
        if printable_ratio < 0.70 or replacement_ratio > 0.15:
            is_broken = True

    # 4. Determine classification
    details = {
        "char_count": char_count,
        "clean_text_len": len(clean_text),
        "raster_coverage": round(raster_coverage, 4),
        "image_count": image_count,
        "is_broken": is_broken,
    }

    if is_broken:
        classification = PageClassification.BROKEN_DIGITAL
    elif len(clean_text) < 20:
        classification = PageClassification.SCANNED
    else:
        if raster_coverage > 0.60:
            classification = PageClassification.MIXED
        else:
            classification = PageClassification.NATIVE

    return PageMetadata(
        page_number=page_number,
        width=float(width),
        height=float(height),
        rotation=rotation,
        classification=classification,
        details=details,
    )
