"""Tests for lossless embedded image extraction from PDF (IMG-001, IMG-003)."""

from pathlib import Path
from PIL import Image
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import BlockType
from openlargeprint.security.isolation import JobWorkspace


def test_lossless_image_extraction(tmp_path: Path):
    """Verify that embedded images are extracted losslessly with correct dimensions and aspect ratio."""
    # Create an image with known dimensions and distinctive aspect ratio (300 x 150 -> 2:1)
    img_path = tmp_path / "diagram.png"
    orig_img = Image.new("RGB", (300, 150), color=(100, 150, 200))
    orig_img.save(img_path)

    # Embed in PDF
    pdf_path = tmp_path / "doc_with_image.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 700, "Figure Description Above")
    c.drawImage(str(img_path), 50, 500, width=300, height=150)
    c.setFont("Helvetica", 11)
    c.drawString(50, 450, "Figure 1.2: Law flow diagram.")
    c.showPage()
    c.save()

    importer = NativePdfImporter()
    with JobWorkspace() as ws:
        doc = importer.import_document(pdf_path, ws)
        
        # Locate image block
        img_blocks = [b for b in doc.blocks if b.type == BlockType.IMAGE]
        assert len(img_blocks) == 1
        
        img_block = img_blocks[0]
        assert img_block.image_asset is not None
        assert img_block.image_asset.width == 300
        assert img_block.image_asset.height == 150
        
        # Aspect ratio check (IMG-003)
        aspect_ratio = img_block.image_asset.width / img_block.image_asset.height
        assert pytest.approx(aspect_ratio, 0.01) == 2.0
        
        # Verify physical file was written to assets directory
        saved_file = Path(img_block.image_asset.file_path)
        assert saved_file.exists()
        
        # Read saved image and check dimensions
        with Image.open(saved_file) as loaded_img:
            assert loaded_img.size == (300, 150)
