from __future__ import annotations

import io
from pathlib import Path
from typing import Callable

import pikepdf
import pypdfium2 as pdfium
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from openlargeprint.ocr.base import CancellationToken, DocumentOcrEngine
from openlargeprint.security.validator import bounded_pdf_scale
from .fonts import ensure_arabic_font

_RENDER_DPI = 200.0
_MIN_TEXT_SIZE = 4.0


def build_searchable_pdf(
    source_pdf: Path | str,
    output_path: Path | str,
    ocr_engine: DocumentOcrEngine | None = None,
    dpi: float = _RENDER_DPI,
    selected_pages: set[int] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> Path:
    source = Path(source_pdf)
    output = Path(output_path)
    if source.resolve() == output.resolve():
        raise ValueError("Choose an output file different from the original document.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with pikepdf.open(source) as original, pdfium.PdfDocument(source) as rendered:
        if selected_pages is not None and (
            not selected_pages or any(type(p) is not int or not 1 <= p <= len(original.pages) for p in selected_pages)
        ):
            raise ValueError("Invalid page selection.")
        for index, target in enumerate(original.pages):
            if selected_pages is not None and index + 1 not in selected_pages:
                continue
            if cancel_check and cancel_check():
                raise InterruptedError("Conversion cancelled.")
            page = rendered[index]
            try:
                textpage = page.get_textpage()
                try:
                    has_text = bool(textpage.get_text_range().strip())
                finally:
                    textpage.close()
                if has_text or ocr_engine is None:
                    continue
                width, height = page.get_size()
                scale = bounded_pdf_scale(width, height, dpi)
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    result = ocr_engine.analyze_page(
                        image, page_num=index + 1, cancellation=CancellationToken(cancel_check)
                    )
                finally:
                    bitmap.close()
                if result.cancelled or (cancel_check and cancel_check()):
                    raise InterruptedError("Conversion cancelled.")
                if not result.lines:
                    continue
                box = [float(v) for v in target.cropbox]
                crop_width, crop_height = box[2] - box[0], box[3] - box[1]
                overlay_bytes = io.BytesIO()
                overlay = canvas.Canvas(overlay_bytes, pagesize=(crop_width, crop_height))
                rotation = int(target.obj.get("/Rotate", 0)) % 360
                if rotation == 90:
                    overlay.translate(crop_width, 0)
                elif rotation == 180:
                    overlay.translate(crop_width, crop_height)
                elif rotation == 270:
                    overlay.translate(0, crop_height)
                overlay.rotate(rotation)
                font = ensure_arabic_font()
                for line in result.lines:
                    if not line.text:
                        continue
                    size = max(_MIN_TEXT_SIZE, line.height / scale)
                    text = overlay.beginText(line.x0 / scale, height - line.y1 / scale)
                    text.setTextRenderMode(3)
                    text.setFont(font, size)
                    text_width = pdfmetrics.stringWidth(line.text, font, size)
                    if text_width > 0:
                        text.setHorizScale(100.0 * line.width / scale / text_width)
                    text.textOut(line.text)
                    overlay.drawText(text)
                overlay.showPage()
                overlay.save()
                overlay_bytes.seek(0)
                with pikepdf.open(overlay_bytes) as layer:
                    target.add_overlay(layer.pages[0], pikepdf.Rectangle(*box))
            finally:
                page.close()
        if cancel_check and cancel_check():
            raise InterruptedError("Conversion cancelled.")
        if selected_pages is not None:
            for index in range(len(original.pages) - 1, -1, -1):
                if index + 1 not in selected_pages:
                    del original.pages[index]
        original.save(output)
    return output


class SearchablePdfExporter:
    def export(
        self,
        source_pdf: Path | str,
        output_path: Path | str,
        ocr_engine: DocumentOcrEngine | None = None,
        dpi: float = _RENDER_DPI,
        selected_pages: set[int] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
        try:
            return build_searchable_pdf(
                source_pdf, output_path, ocr_engine, dpi, selected_pages, cancel_check
            )
        finally:
            close_engine = getattr(ocr_engine, "close", None)
            if callable(close_engine):
                close_engine()
