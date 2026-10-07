"""PDF import: classify, analyse layout, read text, rebuild structure (DOC-001, PDF-001..007).

For every page:

1. Read the page's own text at character level and decide how to treat it.
   Pages whose text is visible are *native* and are never recognised again
   (PDF-002). Pages with no text, an invisible text layer, or text hidden under
   a page-sized picture are *scanned* and go to recognition (PDF-003). Text that
   is garbled is *broken* and also goes to recognition (PDF-005).
2. Run the layout model on the rendered page. It returns titles, paragraphs,
   tables, figures, captions and page furniture in reading order.
3. Fill the regions with words (native or recognised), add fill-in blanks, and
   assemble blocks. Native text regions that have no text but sit on a picture
   are recognised on their own (mixed pages, PDF-004).

A page that fails keeps its original image in the output and is flagged; the
rest of the document is unaffected (UI-003, SPEC §2).
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image

from openlargeprint.importers.base import BaseImporter, CancelCheck, CheckpointCallback, ProgressCallback
from openlargeprint.ir.models import (
    SCHEMA_VERSION,
    Block,
    BlockType,
    BoundingBox,
    DocumentIR,
    DocumentMetadata,
    ExtractionMethod,
    ImageAsset,
    PageClassification,
    PageMetadata,
)
from openlargeprint.layout.detector import get_layout_detector
from openlargeprint.layout.regions import LayoutRegion, RegionKind, TEXT_KINDS, coverage
from openlargeprint.ocr.base import CancellationToken, DocumentOcrEngine
from openlargeprint.ocr.router import OcrRouter, RoutingMode
from openlargeprint.security.isolation import JobWorkspace, log_safe_info
from openlargeprint.security.validator import bounded_pdf_scale
from .assemble import PageAssembler, assign_heading_levels, insert_blanks
from .classifier import classify_pdf_page
from .rules import find_rules
from .scanned import ocr_words
from .tables import build_table, ruled_table_regions
from .textlayer import Word, extract_native_text, page_box

LAYOUT_DPI = 150.0
FIGURE_MIN_DPI = 150.0
FIGURE_MAX_DPI = 300.0
LOW_PAGE_CONFIDENCE = 0.5
REVIEW_CONFIDENCE = 0.75
SHOW_ORIGINAL_CONFIDENCE = 0.7
MIN_NATIVE_CHARS = 40


def _save_image(image: Image.Image, path_stem: Path, alt: str) -> ImageAsset:
    """PNG for line art and flat colour, JPEG for photographs (keeps books a sensible size)."""
    rgb = image.convert("RGB")
    sample = rgb.copy()
    sample.thumbnail((256, 256))
    colours = sample.getcolors(maxcolors=4096)
    if colours is None:
        path = path_stem.with_suffix(".jpg")
        rgb.save(path, format="JPEG", quality=90, optimize=True)
        mime = "image/jpeg"
    else:
        path = path_stem.with_suffix(".png")
        rgb.save(path, format="PNG", optimize=True)
        mime = "image/png"
    return ImageAsset(asset_id=path_stem.name, file_path=str(path), mime_type=mime,
                      width=rgb.width, height=rgb.height, alt_text=alt)


def _language_hint(file_path: Path, sample: str) -> str:
    text = f"{file_path.stem} {sample}"
    return "ar" if sum(1 for c in text if "؀" <= c <= "ۿ") >= 3 or "arabic" in file_path.name.lower() else "en"


class NativePdfImporter(BaseImporter):
    """Imports PDF documents into DocumentIR (DOC-001, PDF-001..007)."""

    def __init__(
        self,
        ocr_engine: Optional[DocumentOcrEngine] = None,
        routing_mode: RoutingMode = RoutingMode.AUTOMATIC,
        ocr_dpi: float = 300.0,
        layout_detector=None,
    ):
        self.routing_mode = RoutingMode(routing_mode)
        self.ocr_dpi = 400.0 if self.routing_mode == RoutingMode.MAXIMUM_ACCURACY else ocr_dpi
        self._router = OcrRouter()
        self._injected_engine = ocr_engine
        self._layout = layout_detector

    @property
    def ocr_engine(self) -> DocumentOcrEngine:
        return self._injected_engine or self._router.get_engine(self.routing_mode)

    def _engine_for(self, language: str) -> DocumentOcrEngine:
        if self._injected_engine is not None:
            return self._injected_engine
        return self._router.get_engine(self.routing_mode, language=language)

    # ------------------------------------------------------------------
    def import_document(
        self,
        file_path: Path,
        workspace: JobWorkspace,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
        checkpoint_callback: Optional[CheckpointCallback] = None,
        selected_pages: Optional[Set[int]] = None,
    ) -> DocumentIR:
        log_safe_info(f"Opening PDF document: {file_path.name}")
        pdf = pdfium.PdfDocument(file_path)
        page_count = len(pdf)
        layout = self._layout or get_layout_detector()
        pages_meta: List[PageMetadata] = []
        all_blocks: List[Block] = []
        heading_sizes: Dict[str, float] = {}
        body_sizes: List[float] = []
        total = len(selected_pages) if selected_pages is not None else page_count
        done = 0
        language = _language_hint(file_path, "")
        try:
            for index in range(page_count):
                page_num = index + 1
                if selected_pages is not None and page_num not in selected_pages:
                    continue
                if cancel_check and cancel_check():
                    raise InterruptedError("Operation cancelled by user.")
                done += 1
                page = pdf[index]
                try:
                    meta = classify_pdf_page(page, page_num)
                    pages_meta.append(meta)
                    marker = Block(id=f"p{page_num}_marker", type=BlockType.PAGE_MARKER,
                                   source_page=page_num, page_marker=page_num)
                    all_blocks.append(marker)
                    if meta.details.get("is_blank"):
                        if progress_callback:
                            progress_callback(done, total, "extracting", f"Reading page {page_num} of {page_count}")
                        if checkpoint_callback:
                            checkpoint_callback(page_num, meta.classification, False, None)
                        continue
                    try:
                        blocks, page_headings, sizes = self._process_page(
                            page, meta, workspace, layout, language, cancel_check,
                            lambda stage, message: progress_callback(done, total, stage, message) if progress_callback else None,
                            page_count,
                        )
                    except InterruptedError:
                        raise
                    except Exception as exc:
                        log_safe_info(f"Page {page_num} could not be converted ({type(exc).__name__})")
                        blocks = [self._preserve_page(page, page_num, workspace,
                                                      f"Page {page_num} could not be converted. The original page is shown instead.")]
                        page_headings, sizes = {}, []
                    heading_sizes.update(page_headings)
                    body_sizes.extend(sizes)
                    sample = " ".join(b.text or "" for b in blocks[:6])
                    if language == "en" and sum(1 for c in sample if "؀" <= c <= "ۿ") > 20:
                        language = "ar"
                    all_blocks.extend(blocks)
                    if checkpoint_callback:
                        warned = next((w for b in blocks for w in b.warnings), None)
                        checkpoint_callback(page_num, meta.classification, warned is not None, warned)
                finally:
                    page.close()
        finally:
            pdf.close()
            self._router.close()
            close = getattr(self._injected_engine, "close", None)
            if callable(close):
                close()

        body = statistics.median(body_sizes) if body_sizes else 11.0
        assign_heading_levels(all_blocks, heading_sizes, body)
        all_blocks = self._settle_page_furniture(all_blocks, pages_meta)
        metadata = DocumentMetadata(
            title=file_path.stem.replace("_", " ").strip(),
            source_file_name=file_path.name,
            page_count=len(pages_meta) if selected_pages is not None else page_count,
        )
        return DocumentIR(schema_version=SCHEMA_VERSION, metadata=metadata, pages=pages_meta, blocks=all_blocks)

    # ------------------------------------------------------------------
    def _process_page(self, page: pdfium.PdfPage, meta: PageMetadata, workspace: JobWorkspace,
                      layout, language: str, cancel_check: Optional[CancelCheck], report, page_count: int,
                      ) -> Tuple[List[Block], Dict[str, float], List[float]]:
        page_num = meta.page_number
        width, height = meta.width, meta.height
        crop = page_box(page)
        textpage = page.get_textpage()
        try:
            native = extract_native_text(page, textpage, height, crop)
        finally:
            textpage.close()

        broken = native.broken_chars > 0.15 * max(1, native.visible_chars)
        # Visible text is the document's own (PDF-002). On a page that is mostly a
        # picture, a few stray characters (a stamped page number) do not make it digital.
        mostly_picture = meta.details.get("raster_coverage", 0) > 0.5
        use_native = not broken and native.visible_chars >= (MIN_NATIVE_CHARS if mostly_picture else 1)
        if broken:
            meta.classification = PageClassification.BROKEN_DIGITAL
        elif not use_native:
            meta.classification = PageClassification.SCANNED
            if native.hidden_chars:
                meta.details["hidden_text_layer"] = True
        recognise = not use_native and self.routing_mode != RoutingMode.NATIVE_ONLY

        if report:
            report("ocr" if recognise else "extracting",
                   f"Recognizing scanned text, page {page_num} of {page_count}" if recognise
                   else f"Reading page {page_num} of {page_count}")

        hi_scale = bounded_pdf_scale(width, height, self.ocr_dpi if recognise else LAYOUT_DPI)
        bitmap = page.render(scale=hi_scale)
        try:
            image = bitmap.to_pil().convert("RGB")
        finally:
            bitmap.close()
        layout_image = image
        if recognise and hi_scale > LAYOUT_DPI / 72.0 * 1.2:
            layout_image = image.resize((int(width * LAYOUT_DPI / 72.0), int(height * LAYOUT_DPI / 72.0)), Image.BILINEAR)

        page_layout = layout.detect(layout_image, width, height)
        regions = page_layout.regions
        if use_native:
            if page_layout.source != "model":
                # Without the layout model, pictures are still found from the file itself.
                regions = regions + self._image_objects(page, native.words, width, height, crop)
            regions = regions + self._vector_artwork(page, regions, native.words, width, height, crop)
        meta.details["layout"] = page_layout.source

        method = ExtractionMethod.NATIVE
        page_confidence = 1.0
        if use_native:
            words: List[Word] = list(native.words)
            words.extend(self._recognise_empty_regions(page, regions, words, meta, language, cancel_check))
            if any(w.confidence < 1.0 for w in words):
                meta.classification = PageClassification.MIXED
        elif recognise:
            method = ExtractionMethod.OCR_MAXIMUM if self.routing_mode == RoutingMode.MAXIMUM_ACCURACY else ExtractionMethod.OCR_FAST
            words, page_confidence = self._recognise(image, hi_scale, page_num, language, cancel_check)
        else:
            words = []

        rules = find_rules(layout_image, width, height,
                           [w.box for w in words if any(ch.isalnum() for ch in w.text)],
                           ink=215 if recognise else 200)
        if page_layout.source != "model":
            regions = regions + [r for r in ruled_table_regions(rules, words)
                                 if not any(coverage(r.box, other.box) > 0.5 for other in regions)]
        words = insert_blanks(words, rules, regions, width)

        figure_counter = [0]

        def make_figure(region: LayoutRegion) -> Optional[ImageAsset]:
            if region.width < 6 or region.height < 6:
                return None
            if region.area < 0.002 * width * height and max(region.width, region.height) < 36:
                meta.details["decorative_images"] = meta.details.get("decorative_images", 0) + 1
                return None
            figure_counter[0] += 1
            stem = workspace.assets_dir / f"p{page_num}_fig{figure_counter[0]}"
            pad = 2.0
            box = (max(0.0, region.x0 - pad), max(0.0, region.y0 - pad),
                   min(width, region.x1 + pad), min(height, region.y1 + pad))
            crop_img = None
            if recognise:
                crop_img = image.crop(tuple(int(v * hi_scale) for v in box))
            else:
                # IMG-001: a picture that is exactly one embedded image, with nothing
                # printed over it, is taken from the file at its own resolution.
                if not any(coverage(w.box, region.box) > 0.5 for w in native.words):
                    crop_img = self._embedded_picture(page, region, height, crop)
                if crop_img is None:
                    dpi = self._figure_dpi(page, region, height, crop)
                    scale = bounded_pdf_scale(width, height, dpi)
                    bm = page.render(scale=scale, crop=(box[0], height - box[3], width - box[2], box[1]))
                    try:
                        crop_img = bm.to_pil()
                    finally:
                        bm.close()
            if crop_img.width < 4 or crop_img.height < 4:
                return None
            return _save_image(crop_img, stem, f"Picture from page {page_num}")

        def make_table(region: LayoutRegion, table_words: List[Word]):
            built = build_table(region, table_words, rules)
            if built is None:
                return None
            structure, confidence = built
            source = make_figure(region) if confidence < 0.6 else None
            if source is not None:
                source.alt_text = f"Original table from page {page_num}"
            return structure, confidence, source

        rtl = language == "ar"
        assembler = PageAssembler(page_num, width, height, method, rtl=rtl)
        assembled = assembler.assemble(regions, words, make_figure, make_table)
        blocks = assembled.blocks
        if assembled.printed_page:
            meta.details["printed_page"] = assembled.printed_page

        if recognise:
            has_text = any(b.text and b.type != BlockType.CAPTION for b in blocks)
            has_pictures = any(b.type == BlockType.IMAGE for b in blocks)
            if not has_text and not has_pictures:
                picture = self._preserve_page(page, page_num, workspace, "")
                picture.warnings.clear()
                picture.confidence = 1.0
                picture.image_asset.alt_text = f"Page {page_num}, a page without text"
                blocks.insert(0, picture)
            elif has_text and page_confidence < LOW_PAGE_CONFIDENCE:
                blocks.insert(0, self._preserve_page(
                    page, page_num, workspace,
                    f"Page {page_num} was hard to read. The original page is shown so nothing is lost."))
            else:
                for block in blocks:
                    if block.text and block.confidence < REVIEW_CONFIDENCE and block.role not in ("running_text", "page_number"):
                        block.warnings.append("Some words here were hard to read. Compare with the original page.")
                        if block.confidence < SHOW_ORIGINAL_CONFIDENCE and block.image_asset is None:
                            block.image_asset = self._crop_original(image, hi_scale, block, height, workspace)
        elif use_native and any(w.visual_order for w in words):
            # Arabic stored in display order cannot be put into reading order without
            # guessing; the stored characters stay as they are, next to the page itself.
            for block in blocks:
                if block.text and block.text_direction.value == "rtl":
                    block.warnings.append("Arabic reading order may be uncertain. Compare with the original page shown here.")
            try:
                blocks.insert(0, self._preserve_page(page, page_num, workspace,
                                                     f"Page {page_num} is shown as printed because its Arabic text order is uncertain."))
            except Exception:
                pass
        elif not use_native:
            blocks.insert(0, self._preserve_page(
                page, page_num, workspace,
                f"Page {page_num} is a picture of text and recognition is turned off, so the original page is shown."))
        return blocks, assembled.heading_sizes, assembled.body_sizes

    # ------------------------------------------------------------------
    def _recognise(self, image: Image.Image, scale: float, page_num: int, language: str,
                   cancel_check: Optional[CancelCheck]) -> Tuple[List[Word], float]:
        engine = self._engine_for(language)
        result = engine.analyze_page(image, page_num=page_num, language_hints=(language,),
                                     cancellation=CancellationToken(cancel_check))
        if result.cancelled or (cancel_check and cancel_check()):
            raise InterruptedError("Conversion cancelled.")
        confidences = [line.confidence for line in result.lines]
        mean = statistics.mean(confidences) if confidences else 0.0
        if self._injected_engine is None and language == "en" and len(result.lines) >= 3 and mean < 0.65:
            # Possibly Arabic: try the Arabic recogniser and keep whichever reads better.
            alternative = self._engine_for("ar").analyze_page(
                image, page_num=page_num, language_hints=("ar",), cancellation=CancellationToken(cancel_check))
            alt_conf = [line.confidence for line in alternative.lines]
            if alt_conf and statistics.mean(alt_conf) > mean + 0.1:
                result, mean = alternative, statistics.mean(alt_conf)
        return ocr_words(result, scale), mean

    def _recognise_empty_regions(self, page, regions: List[LayoutRegion], words: List[Word],
                                 meta: PageMetadata, language: str, cancel_check) -> List[Word]:
        """Mixed pages: text regions with no native text but painted as a picture (PDF-004)."""
        if self.routing_mode == RoutingMode.NATIVE_ONLY or meta.details.get("raster_coverage", 0) < 0.01:
            return []
        empty = [r for r in regions if r.kind in TEXT_KINDS and r.area > 200
                 and not any(coverage(w.box, r.box) > 0.5 for w in words)]
        # Pictures often carry words of their own (speech bubbles, labels, signs).
        pictures = [r for r in regions if r.kind == RegionKind.FIGURE and not r.decorative
                    and r.area > 2500 and not any(coverage(w.box, r.box) > 0.5 for w in words)]
        if not empty and not pictures:
            return []
        width, height = meta.width, meta.height
        scale = bounded_pdf_scale(width, height, self.ocr_dpi)
        found: List[Word] = []
        for region in empty + pictures:
            box = (region.x0, region.y0, region.x1, region.y1)
            bm = page.render(scale=scale, crop=(box[0], height - box[3], width - box[2], box[1]))
            try:
                crop_img = bm.to_pil().convert("RGB")
            finally:
                bm.close()
            if crop_img.width < 8 or crop_img.height < 8:
                continue
            engine = self._engine_for(language)
            result = engine.analyze_page(crop_img, page_num=meta.page_number, language_hints=(language,),
                                         cancellation=CancellationToken(cancel_check))
            if result.cancelled:
                raise InterruptedError("Conversion cancelled.")
            if region in pictures:
                # Only clear words: photographs produce letter-like noise.
                result.lines = [l for l in result.lines if l.confidence >= 0.85
                                and sum(c.isalpha() for c in l.text) >= 2]
            for word in ocr_words(result, scale, offset=(box[0], box[1])):
                word.confidence = min(word.confidence, 0.999)
                found.append(word)
        if empty and found:
            meta.details["recognised_regions"] = len(empty)
        return found

    @staticmethod
    def _image_objects(page, words: List[Word], width: float, height: float, crop) -> List[LayoutRegion]:
        """Embedded pictures as figure regions, used when no layout model is available (IMG-001).

        A picture that fills most of the page with text printed over it is a
        background, not a figure, and is left to the page itself.
        """
        found: List[LayoutRegion] = []
        try:
            objects = list(page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=8))
        except Exception:
            return []
        for obj in objects:
            try:
                left, bottom, right, top = obj.get_bounds()
            except Exception:
                continue
            box = (max(0.0, left - crop[0]), max(0.0, crop[3] - top),
                   min(width, right - crop[0]), min(height, crop[3] - bottom))
            if box[2] - box[0] < 6 or box[3] - box[1] < 6:
                continue
            if (box[2] - box[0]) * (box[3] - box[1]) > 0.6 * width * height and any(
                    coverage(w.box, box) > 0.5 for w in words):
                continue
            if any(coverage(box, r.box) > 0.85 for r in found):
                continue
            found.append(LayoutRegion(RegionKind.FIGURE, *box, score=0.5, label="embedded_image"))
        found.sort(key=lambda r: (r.y0, r.x0))
        for order, region in enumerate(found):
            region.order = order
        return found

    @staticmethod
    def _vector_artwork(page, regions: List[LayoutRegion], words: List[Word], width: float,
                        height: float, crop) -> List[LayoutRegion]:
        """Drawings made of vector paths that the layout model did not mark (IMG-002).

        Paths are clustered; a cluster that is large, holds no text and lies
        outside every detected region is kept as a picture so it is not lost.
        """
        boxes: List[List[float]] = []
        try:
            for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_PATH], max_depth=8):
                left, bottom, right, top = obj.get_bounds()
                boxes.append([left - crop[0], crop[3] - top, right - crop[0], crop[3] - bottom])
        except Exception:
            return []
        clusters: List[List[float]] = []
        for box in sorted(boxes, key=lambda b: (b[1], b[0])):
            for cluster in clusters:
                if (box[0] <= cluster[2] + 6 and box[2] >= cluster[0] - 6
                        and box[1] <= cluster[3] + 6 and box[3] >= cluster[1] - 6):
                    cluster[:] = [min(cluster[0], box[0]), min(cluster[1], box[1]),
                                  max(cluster[2], box[2]), max(cluster[3], box[3])]
                    break
            else:
                clusters.append(list(box))
        found: List[LayoutRegion] = []
        for x0, y0, x1, y1 in clusters:
            w, h = x1 - x0, y1 - y0
            if w < 40 or h < 40 or w * h < 0.03 * width * height or w > 0.98 * width:
                continue
            box = (x0, y0, x1, y1)
            if any(coverage(box, r.box) > 0.3 or coverage(r.box, box) > 0.3 for r in regions):
                continue
            if sum(1 for word in words if coverage(word.box, box) > 0.5) > 2:
                continue  # a frame or ruled box around text, not a drawing
            order = max((r.order for r in regions if r.y1 <= y0), default=-1) + 0.5
            found.append(LayoutRegion(RegionKind.FIGURE, x0, y0, x1, y1, score=0.5, order=order,
                                      label="vector_artwork"))
        return found

    @staticmethod
    def _embedded_picture(page, region: LayoutRegion, height: float, crop) -> Optional[Image.Image]:
        """The decoded embedded image behind a figure, masks applied, at its own pixel size."""
        from openlargeprint.security.validator import validate_image_dimensions

        matches = []
        try:
            for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=8):
                left, bottom, right, top = obj.get_bounds()
                box = (left - crop[0], crop[3] - top, right - crop[0], crop[3] - bottom)
                if coverage(box, region.box) >= 0.85 and coverage(region.box, box) >= 0.85:
                    matches.append(obj)
                elif coverage(box, region.box) > 0.2:
                    return None  # several pictures make up this figure: render it as seen
        except Exception:
            return None
        if len(matches) != 1:
            return None
        obj = matches[0]
        try:
            validate_image_dimensions(*obj.get_px_size())
            bitmap = obj.get_bitmap(render=True, scale_to_original=True)
            try:
                picture = bitmap.to_pil().copy()
            finally:
                bitmap.close()
        except Exception:
            return None
        if picture.mode in ("RGBA", "LA", "P"):
            canvas = Image.new("RGB", picture.size, "white")
            canvas.paste(picture.convert("RGBA"), mask=picture.convert("RGBA").split()[-1])
            picture = canvas
        return picture

    @staticmethod
    def _figure_dpi(page, region: LayoutRegion, height: float, crop) -> float:
        """Render figures at the resolution of the picture inside them, within sensible limits."""
        best = FIGURE_MIN_DPI
        try:
            for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=8):
                left, bottom, right, top = obj.get_bounds()
                box = (left - crop[0], crop[3] - top, right - crop[0], crop[3] - bottom)
                if coverage(region.box, box) < 0.3 and coverage(box, region.box) < 0.5:
                    continue
                px_w, _ = obj.get_px_size()
                if right - left > 0:
                    best = max(best, px_w / ((right - left) / 72.0))
        except Exception:
            pass
        return max(FIGURE_MIN_DPI, min(FIGURE_MAX_DPI, best))

    @staticmethod
    def _crop_original(image: Image.Image, scale: float, block: Block, page_height: float,
                       workspace: JobWorkspace) -> Optional[ImageAsset]:
        """The printed lines behind a doubtful block, shown with the recognised text."""
        box = block.source_bounding_box
        if box is None:
            return None
        pad = 4.0
        left = max(0, int((box.x0 - pad) * scale))
        top = max(0, int((page_height - box.y1 - pad) * scale))
        right = min(image.width, int((box.x1 + pad) * scale))
        bottom = min(image.height, int((page_height - box.y0 + pad) * scale))
        if right - left < 8 or bottom - top < 8:
            return None
        asset = _save_image(image.crop((left, top, right, bottom)),
                            workspace.assets_dir / f"{block.id}_original",
                            f"Original lines from page {block.source_page}")
        return asset

    def _preserve_page(self, page: pdfium.PdfPage, page_num: int, workspace: JobWorkspace,
                       warning: str) -> Block:
        width, height = page.get_size()
        scale = bounded_pdf_scale(width, height, 150.0)
        bitmap = page.render(scale=scale)
        try:
            asset = _save_image(bitmap.to_pil(), workspace.assets_dir / f"p{page_num}_retained",
                                f"Original page {page_num}")
        finally:
            bitmap.close()
        asset.asset_id = f"p{page_num}_retained"
        return Block(
            id=f"p{page_num}_retained", type=BlockType.IMAGE, source_page=page_num,
            source_bounding_box=BoundingBox(x0=0, y0=0, x1=width, y1=height),
            image_asset=asset, confidence=0.0, warnings=[warning],
        )

    @staticmethod
    def _settle_page_furniture(blocks: List[Block], pages: List[PageMetadata]) -> List[Block]:
        """Running heads, footers and page numbers move into page details.

        Text that repeats on several pages (book title, chapter name, page
        numbers) is page furniture: it is kept in the page's metadata and shown
        with the page marker instead of interrupting the reading flow. Footer
        text that appears only once is real content and stays as a note.
        """
        meta_by_page = {p.page_number: p for p in pages}

        def normal(text: str) -> str:
            return re.sub(r"[\d\W_]+", " ", text.lower()).strip()

        counts = Counter()
        seen = defaultdict(set)
        for block in blocks:
            if block.role == "running_text" and block.text:
                key = normal(block.text)
                if key and block.source_page not in seen[key]:
                    seen[key].add(block.source_page)
                    counts[key] += 1
        threshold = 2 if len(pages) <= 6 else 3
        kept: List[Block] = []
        for block in blocks:
            meta = meta_by_page.get(block.source_page)
            if block.role == "page_number" and block.text:
                if meta is not None:
                    meta.details.setdefault("printed_page", block.text)
                continue
            if block.role == "edge_text":
                if meta is not None:
                    meta.details.setdefault("edge_text", []).append(block.text or "")
                continue
            if block.role == "running_text" and block.text:
                key = normal(block.text)
                if not key or counts[key] >= threshold:
                    if meta is not None:
                        meta.details.setdefault("running_text", []).append(block.text)
                    continue
                block.role = "page_note"
            kept.append(block)
        return kept
