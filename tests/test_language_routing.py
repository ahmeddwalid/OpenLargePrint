"""Script routing and right-to-left text (OCR-004, LANG-001, LANG-002)."""

from PIL import Image

from openlargeprint.importers.pdf.textlayer import _Char, _chars_to_words
from openlargeprint.importers.pdf.assemble import group_lines


def _char(ch: str, x0: float, width: float = 6.0) -> _Char:
    return _Char(ch, x0, 100.0, x0 + width, 112.0, 110.0, 10.0, False, False, False)


def test_native_arabic_glyphs_form_whole_words_in_reading_order():
    # "سلام عليكم" painted right to left, the way PDFs store Arabic glyphs.
    chars, x = [], 300.0
    for word in ("سلام", "عليكم"):
        for ch in word:
            x -= 6.0
            chars.append(_char(ch, x))
        x -= 5.0
    words = _chars_to_words(chars)
    assert [w.text for w in words] == ["سلام", "عليكم"]
    lines = group_lines(words)
    assert lines[0].text == "سلام عليكم"


def test_latin_inside_arabic_keeps_its_order():
    chars, x = [], 300.0
    for ch in "عقارات":
        x -= 6.0
        chars.append(_char(ch, x))
    x -= 22.0
    for ch in "ISO":
        chars.append(_char(ch, x))
        x += 6.0
    words = _chars_to_words(chars)
    texts = [w.text for w in group_lines(words)[0].words]
    assert texts == ["عقارات", "ISO"]


def test_native_only_retains_scan_without_recognition(tmp_path):
    from openlargeprint.importers.pdf.native import NativePdfImporter
    from openlargeprint.ocr.router import RoutingMode
    from openlargeprint.qa.corpus_builder import BenchmarkCorpusBuilder
    from openlargeprint.security.isolation import JobWorkspace
    from openlargeprint.ir.models import BlockType, ExtractionMethod

    calls = []

    class NoOcr:
        def analyze_page(self, *args, **kwargs):
            calls.append(True)
            raise AssertionError("Native-only mode must never run recognition")

    path = BenchmarkCorpusBuilder(tmp_path).build_mixed_digital_scan()
    with JobWorkspace() as workspace:
        doc = NativePdfImporter(ocr_engine=NoOcr(), routing_mode=RoutingMode.NATIVE_ONLY).import_document(path, workspace)
    assert doc.metadata.page_count == 2
    assert calls == []
    assert any(b.source_page == 1 and b.extraction_method == ExtractionMethod.NATIVE and b.text for b in doc.blocks)
    assert any(b.source_page == 2 and b.type == BlockType.IMAGE and b.image_asset for b in doc.blocks)
    assert not any(b.extraction_method in (ExtractionMethod.OCR_FAST, ExtractionMethod.OCR_MAXIMUM)
                   for b in doc.blocks if b.text)


def test_arabic_file_name_routes_scans_to_the_arabic_recogniser(tmp_path):
    from reportlab.pdfgen import canvas
    from openlargeprint.importers.pdf.native import NativePdfImporter
    from openlargeprint.ocr.base import EnginePageResult
    from openlargeprint.security.isolation import JobWorkspace

    picture = tmp_path / "scan.png"
    Image.new("RGB", (600, 800), (250, 250, 250)).save(picture)
    source = tmp_path / "arabic_contract.pdf"
    pdf = canvas.Canvas(str(source))
    pdf.drawImage(str(picture), 0, 0, width=595, height=842)
    pdf.showPage()
    pdf.save()

    seen = []
    importer = NativePdfImporter()

    class Engine:
        def analyze_page(self, image, *, page_num, language_hints=("en",), cancellation=None):
            seen.append(language_hints)
            return EnginePageResult(lines=[])

    importer._engine_for = lambda language: (seen.append(language), Engine())[1]
    with JobWorkspace() as workspace:
        importer.import_document(source, workspace)
    assert "ar" in seen
