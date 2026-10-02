"""Language routing must use installed verified packs (OCR-004, LANG-002)."""
from pathlib import Path

from PIL import Image

from openlargeprint.ocr.router import OcrRouter
from openlargeprint.ocr.paddle_engine import PaddleRapidOcrEngine


def test_scanned_page_routes_language_and_mode(tmp_path):
    import pypdfium2 as pdfium
    from reportlab.pdfgen import canvas
    from openlargeprint.importers.pdf.scanned import ScannedPageExtractor
    from openlargeprint.ocr.base import EnginePageResult
    from openlargeprint.ocr.router import RoutingMode

    calls = []
    class Engine:
        def analyze_page(self, image, **kwargs):
            calls.append(kwargs["language_hints"])
            return EnginePageResult(lines=[])
    class Router:
        def get_engine(self, mode, language):
            calls.append((mode, language))
            return Engine()
    path = tmp_path / "scan.pdf"
    c = canvas.Canvas(str(path)); c.showPage(); c.save()
    with pdfium.PdfDocument(path) as pdf:
        page = pdf[0]
        try:
            extractor = ScannedPageExtractor(Engine(), ocr_router=Router())
            extractor.extract_page(page, 1, 1, language_hints=("ar",))
        finally:
            page.close()
    assert calls == [(RoutingMode.AUTOMATIC, "ar"), ("ar",)]


def test_router_closes_each_recognizer_once():
    closed = []
    class Engine:
        def close(self):
            closed.append(self)
    router = OcrRouter()
    router._default_engine = Engine()
    router._arabic_engine = Engine()
    router.close()
    assert closed == [router._default_engine, router._arabic_engine]


def test_native_logical_arabic_is_not_guessed_or_reversed(monkeypatch):
    from openlargeprint.importers.pdf import native
    text = "مثلا"
    class TextPage:
        def count_chars(self): return len(text)
        def get_charbox(self, index): return (10 + index * 10, 10, 20 + index * 10, 22)
        def get_textobj(self, index): return None
    monkeypatch.setattr(native.pdfium_c, "FPDFText_GetUnicode", lambda page, index: ord(text[index]))
    lines = native.NativePdfImporter()._extract_raw_lines(TextPage(), 1)
    assert "".join(line.text for line in lines) == text


def test_installed_arabic_pack_uses_bundled_dictionary(tmp_path, monkeypatch):
    from openlargeprint.models import model_manager
    model = tmp_path / "arabic.onnx"
    model.write_bytes(b"unit fixture")
    untrusted_dict = tmp_path / "arabic_dict.txt"
    untrusted_dict.write_text("altered decoder vocabulary", encoding="utf-8")
    monkeypatch.setattr(model_manager, "get_model_path", lambda *args, **kwargs: model)
    engine = OcrRouter()._init_arabic_engine()
    assert engine is not None
    assert engine.language == "ar"
    assert Path(engine.rec_keys_path).is_file()
    assert Path(engine.rec_keys_path) != untrusted_dict


def test_maximum_mode_keeps_its_warning_for_arabic():
    from openlargeprint.ocr.router import RoutingMode
    router = OcrRouter()
    router._arabic_engine = PaddleRapidOcrEngine(language="ar")
    engine = router.get_engine(RoutingMode.MAXIMUM_ACCURACY, language="ar")
    assert engine is not router._arabic_engine


def test_installed_accuracy_engine_is_cached_and_closed(tmp_path, monkeypatch):
    from openlargeprint.ocr.router import RoutingMode
    from openlargeprint.ocr.modern_engine import ModernRapidOcrEngine
    monkeypatch.setattr(OcrRouter, "_modern_model_path", staticmethod(lambda language: tmp_path / "verified.onnx" if language == "en" else None))
    router = OcrRouter()
    engine = router.get_engine(RoutingMode.MAXIMUM_ACCURACY)
    assert isinstance(engine, ModernRapidOcrEngine)
    assert router.get_engine(RoutingMode.MAXIMUM_ACCURACY) is engine
    closed = []
    monkeypatch.setattr(engine, "close", lambda: closed.append(True))
    router.close()
    assert closed == [True]


def test_unreadable_optional_cache_does_not_break_baseline(monkeypatch):
    import importlib.util
    import importlib.metadata
    from openlargeprint.models import model_manager
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "3.9.2")
    def denied(*args, **kwargs):
        raise PermissionError("Optional cache is unreadable")
    monkeypatch.setattr(model_manager, "get_model_path", denied)
    assert OcrRouter.available_accuracy_languages() == []


def test_native_only_mixed_page_keeps_text_when_evidence_fails(tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from openlargeprint.importers.pdf.native import NativePdfImporter
    from openlargeprint.ocr.router import RoutingMode
    from openlargeprint.security.isolation import JobWorkspace
    from openlargeprint.ir.models import PageClassification
    source = tmp_path / "mixed.pdf"
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (400, 400), "gray").save(image_path)
    pdf = canvas.Canvas(str(source), pagesize=A4)
    text = "Native wording remains intact when page evidence fails."
    pdf.drawString(72, 760, text)
    pdf.drawImage(str(image_path), 72, 80, width=500, height=660)
    pdf.showPage(); pdf.save()
    importer = NativePdfImporter(routing_mode=RoutingMode.NATIVE_ONLY)
    def fail(*args, **kwargs):
        raise OSError("Evidence preparation failed")
    monkeypatch.setattr(importer, "_preserve_page", fail)
    with JobWorkspace() as workspace:
        doc = importer.import_document(source, workspace)
    assert doc.pages[0].classification == PageClassification.MIXED
    assert any(block.text == text for block in doc.blocks)
    assert any("retained" in warning.lower() for block in doc.blocks for warning in block.warnings)


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
    assert any(block.source_page == 1 and block.extraction_method == ExtractionMethod.NATIVE and block.text for block in doc.blocks)
    assert any(block.source_page == 2 and block.type == BlockType.IMAGE and block.image_asset for block in doc.blocks)
    assert not any(block.extraction_method in (ExtractionMethod.OCR_FAST, ExtractionMethod.OCR_MAXIMUM) for block in doc.blocks if block.text)


def test_unsupported_language_has_visible_warning(monkeypatch):
    engine = PaddleRapidOcrEngine()
    monkeypatch.setattr(engine, "_get_engine", lambda: lambda image: ([], []))
    result = engine._analyze_page(Image.new("RGB", (100, 100)), page_num=1,
                                  language_hints=("ar",))
    assert any("language" in warning.lower() and "review" in warning.lower()
               for warning in result.warnings)
