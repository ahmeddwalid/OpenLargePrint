"""Retain unrecognized graphic regions after text/table masking (IMG-002)."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from openlargeprint.ir.models import Block, BlockType, BoundingBox, ExtractionMethod, ImageAsset


def extract_scanned_figures(image, occupied_pixels, page_num: int, scale: float,
                            assets_dir: Path) -> list[Block]:
    # Analyse a small bitmap; retain crops from the full bounded source raster.
    factor = min(1.0, 1000 / max(image.size))
    small = image.resize((max(1, round(image.width * factor)), max(1, round(image.height * factor))))
    try:
        gray = np.array(small.convert("L"))
    finally:
        small.close()
    ink = np.where(gray < 210, 255, 0).astype(np.uint8)
    for left, top, right, bottom in occupied_pixels:
        x0, y0 = max(0, int(left * factor) - 3), max(0, int(top * factor) - 3)
        x1, y1 = min(ink.shape[1], int(right * factor) + 4), min(ink.shape[0], int(bottom * factor) + 4)
        ink[y0:y1, x0:x1] = 0
    connected = cv2.dilate(ink, np.ones((9, 9), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(connected)
    blocks = []
    for index in range(1, count):
        x, y, width, height, area = stats[index]
        if min(width, height) < 25 or area < ink.size * .003:
            continue
        x0, y0 = max(0, int(x / factor) - 3), max(0, int(y / factor) - 3)
        x1, y1 = min(image.width, int((x + width) / factor) + 3), min(image.height, int((y + height) / factor) + 3)
        asset_id = f"p{page_num}_scan_figure{index}"
        path = assets_dir / f"{asset_id}.png"
        with image.crop((x0, y0, x1, y1)) as crop:
            crop.save(path, format="PNG")
            asset = ImageAsset(asset_id=asset_id, file_path=str(path), width=crop.width,
                               height=crop.height, alt_text=f"Retained source region from page {page_num}")
        blocks.append(Block(id=asset_id, type=BlockType.IMAGE, source_page=page_num,
                            source_bounding_box=BoundingBox(x0=x0 / scale, x1=x1 / scale,
                                y0=(image.height - y1) / scale, y1=(image.height - y0) / scale),
                            image_asset=asset, extraction_method=ExtractionMethod.OCR_FAST,
                            confidence=.8, warnings=["A source graphic region was retained. Check its position against the original."]))
    return blocks
