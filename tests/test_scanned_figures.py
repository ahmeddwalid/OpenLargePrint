"""Raster figures survive scanned-page reflow (IMG-002, PDF-006)."""
from PIL import Image, ImageDraw
from openlargeprint.importers.pdf.figures import extract_scanned_figures


def test_crops_figures_but_not_recognized_text(tmp_path):
    image = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 40, 450, 60), fill="black")
    draw.rectangle((100, 200, 400, 400), outline="black", width=8)
    draw.line((100, 200, 400, 400), fill="black", width=8)
    figures = extract_scanned_figures(image, [(45, 35, 455, 65)], 1, 1, tmp_path)
    assert len(figures) == 1
    bbox = figures[0].source_bounding_box
    assert bbox.y1 < 800 - 65
    assert bbox.x0 <= 100 and bbox.x1 >= 400
    with Image.open(figures[0].image_asset.file_path) as retained:
        assert retained.width >= 300


def test_recognized_text_alone_does_not_become_figure(tmp_path):
    image = Image.new("RGB", (600, 800), "white")
    ImageDraw.Draw(image).rectangle((50, 40, 450, 60), fill="black")
    assert extract_scanned_figures(image, [(45, 35, 455, 65)], 1, 1, tmp_path) == []
