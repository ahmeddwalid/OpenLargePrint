"""Content must survive reconstruction unchanged (PDF-002, OCR-007, DOC-002)."""
from openlargeprint.importers.pdf.native import NativePdfImporter, TextLine
from openlargeprint.importers.pdf.scanned import ScannedPageExtractor, OcrPointLine


def line(text, y, x=50):
    return TextLine(text, (x, y, x + 200, y + 12), 12, "Helvetica", False, 2)


def test_native_margin_text_is_preserved():
    importer = NativePdfImporter()
    lines = [line("A meaningful heading", 740), line("Body text.", 500), line("© Author 2024", 30)]
    blocks = importer._form_semantic_blocks(
        importer._filter_running_headers_and_footers(lines, 2, 600, 800), 2, 1, 800, 600
    )
    text = " ".join(b.text or "" for b in blocks)
    assert "A meaningful heading" in text
    assert "© Author 2024" in text


def test_native_hyphens_and_spaced_letters_are_preserved():
    blocks = NativePdfImporter()._form_semantic_blocks(
        [line("A B C and well-", 500), line("known words.", 484)], 2, 1, 800, 600
    )
    text = " ".join(b.text or "" for b in blocks)
    assert "A B C" in text
    assert "well-" in text


def test_native_word_gap_is_readable_at_small_source_font(tmp_path):
    import pypdfium2 as pdfium
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.pdfmetrics import stringWidth
    source = tmp_path / "small-text.pdf"
    sheet = canvas.Canvas(str(source))
    sheet.setFont("Helvetica", 8)
    sheet.drawString(50, 700, "Small")
    sheet.drawString(50 + stringWidth("Small", "Helvetica", 8) + 1, 700, "words")
    sheet.save()
    with pdfium.PdfDocument(source) as pdf:
        page = pdf[0]
        textpage = page.get_textpage()
        try:
            lines = NativePdfImporter()._extract_raw_lines(textpage, 1)
            assert "Small words" in " ".join(line.text for line in lines)
        finally:
            textpage.close()


def test_scanned_hyphens_and_letter_bullets_are_preserved():
    extractor = ScannedPageExtractor(None)
    lines = [OcrPointLine("O", 50, 500, 60, 512, .9),
             OcrPointLine("well-", 70, 500, 270, 512, .9),
             OcrPointLine("known words.", 70, 484, 270, 496, .9)]
    text = " ".join(b.text or "" for b in extractor._cluster_semantic_blocks(lines, 2, 1, [], 800))
    assert "O" in text
    assert "well-" in text


def test_failed_table_crop_keeps_native_text(tmp_path, monkeypatch):
    import pypdfium2 as pdfium
    from reportlab.pdfgen import canvas
    from openlargeprint.pipeline import PipelineOrchestrator
    from openlargeprint.ir.models import BlockType, ExtractionMethod
    source = tmp_path / "table.pdf"
    sheet = canvas.Canvas(str(source))
    for y, left, right in [(700, "Item", "Value"), (680, "Original", "12"), (660, "Repeated", "34")]:
        sheet.drawString(60, y, left)
        sheet.drawString(300, y, right)
    sheet.save()
    original = pdfium.PdfPage.render
    def fail_crop(page, *args, **kwargs):
        if "crop" in kwargs:
            raise RuntimeError("crop unavailable")
        return original(page, *args, **kwargs)
    monkeypatch.setattr(pdfium.PdfPage, "render", fail_crop)
    result = PipelineOrchestrator().convert(source, tmp_path / "out.pdf", export_format="pdf")
    tables = [b for b in result.document_ir.blocks if b.type == BlockType.TABLE]
    assert tables and tables[0].extraction_method == ExtractionMethod.NATIVE
    assert tables[0].table_structure.rows[1][0].text == "Original"
    assert any("source table image" in w for w in tables[0].warnings)


def test_mixed_page_preserves_column_order(monkeypatch):
    from types import SimpleNamespace
    from openlargeprint.ir.models import Block, BlockType, BoundingBox, PageMetadata, PageClassification
    importer = NativePdfImporter()
    blocks = [Block(id=name, type=BlockType.PARAGRAPH, text=name, source_page=1,
        source_bounding_box=BoundingBox(x0=x, y0=y, x1=x+180, y1=y+30))
        for name, x, y in [("left top", 50, 600), ("left bottom", 50, 500),
                           ("right top", 350, 600), ("right bottom", 350, 500)]]
    monkeypatch.setattr(importer, "_extract_native_text", lambda *args: blocks)
    monkeypatch.setattr(importer.scanned_extractor, "extract_page", lambda *args, **kwargs: [])
    textpage = SimpleNamespace(count_rects=lambda: 0, close=lambda: None)
    page = SimpleNamespace(get_textpage=lambda: textpage)
    meta = PageMetadata(page_number=1, width=600, height=800, classification=PageClassification.MIXED)
    result = importer._reconcile_mixed_page(page, 1, 1, meta)
    assert [b.id for b in result] == [b.id for b in blocks]


def test_inconsistent_scan_columns_are_not_consumed_as_table():
    from PIL import Image
    extractor = ScannedPageExtractor(object())
    lines = [OcrPointLine(f"Column {column}", 30 + column * 170, y,
                         130 + column * 170, y + 12, .9)
             for row, y in enumerate((700, 680, 660))
             for column in range(3 if row != 1 else 2)]
    remaining, tables = extractor._extract_tables(lines, 1, 1, 600, 800,
                                                 Image.new("RGB", (600, 800)), 1)
    assert not tables
    assert remaining == lines


def test_three_columns_are_read_one_column_at_a_time():
    scans = [OcrPointLine(f"Column{column} row{row}", 30 + column * 190, y,
                         160 + column * 190, y + 12, .9)
             for column in range(3) for row, y in enumerate((700, 680, 660))]
    ordered = ScannedPageExtractor(None)._order_lines_by_columns(scans, 600, 800)
    assert [line.text for line in ordered] == [line.text for line in scans]
    native = [TextLine(item.text, (item.x0, item.y0, item.x1, item.y1),
                       12, "Helvetica", False, 2) for item in scans]
    ordered = NativePdfImporter()._order_lines_by_layout(native, 600, 800)
    assert [line.text for line in ordered] == [line.text for line in native]

    scans = [OcrPointLine(f"Column{column} row{row}", x0, y, x1, y + 12, .9)
             for column, (x0, x1) in enumerate(((50, 140), (500, 590), (800, 840), (900, 940)))
             for row, y in enumerate((700, 680, 660))]
    ordered = ScannedPageExtractor(None)._order_lines_by_columns(scans, 1000, 800)
    assert [line.text for line in ordered] == [line.text for line in scans]
    native = [TextLine(item.text, (item.x0, item.y0, item.x1, item.y1),
                       12, "Helvetica", False, 2) for item in scans]
    ordered = NativePdfImporter()._order_lines_by_layout(native, 1000, 800)
    assert [line.text for line in ordered] == [line.text for line in native]


def test_uncertain_ocr_keeps_raw_text_and_source_page(tmp_path, monkeypatch):
    from PIL import Image, ImageDraw
    from reportlab.pdfgen import canvas
    from openlargeprint.pipeline import PipelineOrchestrator
    from openlargeprint.ir.models import Block, BlockType, BoundingBox, ExtractionMethod
    scan = Image.new("RGB", (600, 800), "white")
    ImageDraw.Draw(scan).rectangle((60, 80, 500, 100), fill="black")
    scan.save(tmp_path / "scan.png")
    source = tmp_path / "uncertain.pdf"
    sheet = canvas.Canvas(str(source), pagesize=(600, 800))
    sheet.drawString(60, 700, "Native page")
    sheet.showPage()
    sheet.drawImage(str(tmp_path / "scan.png"), 0, 0, width=600, height=800)
    sheet.save()
    raw = "Il1 O0 - A B C well- known."
    def uncertain(*args, **kwargs):
        return [Block(id="uncertain", type=BlockType.PARAGRAPH, text=raw,
            source_page=2, source_bounding_box=BoundingBox(x0=60,y0=680,x1=500,y1=720),
            extraction_method=ExtractionMethod.OCR_FAST, confidence=.4,
            warnings=["Some characters are uncertain."])]
    monkeypatch.setattr(ScannedPageExtractor, "extract_page", uncertain)
    result = PipelineOrchestrator().convert(source, tmp_path / "out.pdf", export_format="pdf")
    assert next(b for b in result.document_ir.blocks if b.id == "uncertain").text == raw
    assert any(b.image_asset and b.image_asset.asset_id == "p2_retained" for b in result.document_ir.blocks)
    def failed_evidence(*args, **kwargs):
        raise OSError("Evidence unavailable")
    monkeypatch.setattr(NativePdfImporter, "_preserve_page", failed_evidence)
    result = PipelineOrchestrator().convert(source, tmp_path / "no-evidence.pdf", export_format="pdf")
    retained = next(b for b in result.document_ir.blocks if b.id == "uncertain")
    assert retained.text == raw
    assert any("image could not be prepared" in warning for warning in retained.warnings)


def test_native_rectangles_do_not_duplicate_characters(tmp_path):
    from reportlab.pdfgen import canvas
    import pypdfium2 as pdfium
    path = tmp_path / "overlap.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(50, 700, "Keep repeated words repeated words.")
    c.setFont("Helvetica", 20)
    c.drawString(50, 695, "Overlapping bounds retain every character.")
    c.save()
    importer = NativePdfImporter()
    with pdfium.PdfDocument(path) as doc:
        page = doc[0]
        textpage = page.get_textpage()
        try:
            lines = importer._extract_raw_lines(textpage, 1)
            text = " ".join(l.text for l in lines)
            assert text.count("repeated words") == 2
            assert text.count("retain every character") == 1
        finally:
            textpage.close()
            page.close()


def test_confirmed_blank_page_skips_ocr(tmp_path):
    from reportlab.pdfgen import canvas
    from openlargeprint.security.isolation import JobWorkspace
    from openlargeprint.ir.models import BlockType
    path = tmp_path / "blank.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(50, 700, "A native page before the blank page.")
    c.showPage()
    c.showPage()
    c.drawString(50, 700, "A native page after the blank page.")
    c.save()
    class NoOcr:
        def analyze_page(self, *args, **kwargs):
            raise AssertionError("Blank pages do not need OCR")
    with JobWorkspace() as workspace:
        doc = NativePdfImporter(ocr_engine=NoOcr()).import_document(path, workspace)
    assert len(doc.pages) == 3
    assert not any(b.warnings for b in doc.blocks if b.source_page == 2)
    assert [b.type for b in doc.blocks if b.source_page == 2] == [BlockType.PAGE_MARKER]
