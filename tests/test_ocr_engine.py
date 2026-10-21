"""OCR engine abstraction and the bundled PP-OCR adapter (OCR-001, OCR-002, OCR-004, OCR-006)."""

from PIL import Image, ImageDraw, ImageFont

from openlargeprint.ocr import (
    CancellationToken,
    DocumentOcrEngine,
    EngineCapabilities,
    OcrRouter,
    PaddleRapidOcrEngine,
    RoutingMode,
)


def _text_image(text: str, size=(900, 120)) -> Image.Image:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except OSError:
        from openlargeprint.exporters.fonts import bundled_font_dir
        font = ImageFont.truetype(str(bundled_font_dir() / "DejaVuSans.ttf"), 36)
    draw.text((20, 35), text, fill="black", font=font)
    return image


def test_paddle_engine_conforms_to_protocol():
    engine = PaddleRapidOcrEngine()
    try:
        assert isinstance(engine, DocumentOcrEngine)
        caps = engine.capabilities()
        assert isinstance(caps, EngineCapabilities)
        assert caps.supports_confidence is True
        assert "en" in caps.supported_languages
        assert caps.is_gpu_accelerated is False
    finally:
        engine.close()


def test_recognition_keeps_word_spacing_and_word_boxes():
    engine = PaddleRapidOcrEngine()
    try:
        result = engine.analyze_page(_text_image("Judicial review of public bodies"), page_num=1)
    finally:
        engine.close()
    text = " ".join(line.text for line in result.lines)
    assert "Judicial review" in text and "public bodies" in text
    assert all(line.confidence > 0.8 for line in result.lines)
    words = [word for line in result.lines for word in line.words]
    assert len(words) >= 5
    assert all(word.polygon for word in words)


def test_router_returns_one_cpu_engine_per_script():
    router = OcrRouter()
    try:
        english = router.get_engine(RoutingMode.AUTOMATIC)
        assert router.get_engine(RoutingMode.FAST) is english
        assert router.get_engine(RoutingMode.MAXIMUM_ACCURACY) is english
        arabic = router.get_engine(RoutingMode.AUTOMATIC, language="ar")
        assert arabic is not english
        assert arabic.language == "ar"
        assert english.use_gpu is False and arabic.use_gpu is False
    finally:
        router.close()


def test_router_closes_each_recognizer_once():
    closed = []

    class Engine:
        def close(self):
            closed.append(self)

    router = OcrRouter()
    router._engines = {"en": Engine(), "ar": Engine()}
    engines = list(router._engines.values())
    router.close()
    assert closed == engines
    router.close()
    assert closed == engines


def test_cancelled_token_skips_recognition():
    token = CancellationToken()
    token.cancel()
    engine = PaddleRapidOcrEngine()
    try:
        result = engine.analyze_page(Image.new("RGB", (500, 120), "white"), page_num=1, cancellation=token)
    finally:
        engine.close()
    assert result.cancelled is True
    assert result.lines == []


def test_arabic_recognition_output_is_put_in_reading_order():
    # The Arabic recogniser reads left to right; RapidOCR turns its output into
    # reading order with python-bidi. Without that package every Arabic page fails.
    from rapidocr.utils.utils import reorder_bidi_for_display
    assert reorder_bidi_for_display(("مالس",)) == ("سلام",)
    # Numbers and Latin words inside Arabic keep their own direction.
    assert reorder_bidi_for_display(("2024 ماع",)) == ("عام 2024",)


def _arabic_image(text: str) -> Image.Image:
    import arabic_reshaper
    from PIL import features
    from openlargeprint.exporters.fonts import arabic_choice, font_path
    shown = text if features.check_feature("raqm") else arabic_reshaper.reshape(text)[::-1]
    image = Image.new("RGB", (1100, 120), "white")
    font = ImageFont.truetype(str(font_path(arabic_choice("noto-naskh-arabic"))), 44)
    ImageDraw.Draw(image).text((30, 25), shown, fill="black", font=font)
    return image


def test_arabic_recognition_reads_words_in_reading_order():
    # Needs python-bidi: without it RapidOCR's Arabic recogniser fails on every page.
    engine = PaddleRapidOcrEngine(language="ar")
    try:
        result = engine.analyze_page(_arabic_image("العقد شريعة المتعاقدين"), page_num=1)
    finally:
        engine.close()
    text = " ".join(line.text for line in result.lines)
    assert "العقد شريعة المتعاقدين" in text, text

