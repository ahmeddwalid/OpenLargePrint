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
from openlargeprint.ocr.paddle_engine import arabic_visual_to_logical


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


def test_arabic_visual_order_becomes_reading_order():
    # Recognisers read left to right; Arabic is stored right to left.
    assert arabic_visual_to_logical("مالس") == "سلام"
    # Numbers and Latin words inside Arabic keep their own direction.
    assert arabic_visual_to_logical("2024 ماع") == "عام 2024"
