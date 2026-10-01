"""Real spawned worker recovery and cancellation (UI-002..003, SEC-008)."""
import pytest
from PIL import Image, ImageDraw
from openlargeprint.ocr.worker import OcrWorker
from openlargeprint.ocr.base import CancellationToken


def test_worker_restarts_after_timeout():
    image = Image.new("RGB", (700, 180), "white")
    ImageDraw.Draw(image).text((30, 40), "Judicial Review", fill="black", font_size=36)
    worker = OcrWorker(False, timeout_seconds=.001)
    try:
        with pytest.raises(TimeoutError):
            worker.analyze_page(image, page_num=2, language_hints=("en",), cancellation=None)
        assert worker._process is None
        worker.timeout_seconds = 120
        result = worker.analyze_page(image, page_num=3, language_hints=("en",), cancellation=None)
        assert any("Judicial" in line.text for line in result.lines)
    finally:
        worker.close()
        image.close()


def test_worker_cancelled_before_start():
    worker = OcrWorker(False)
    token = CancellationToken()
    token.cancel()
    with Image.new("RGB", (20, 20)) as image:
        result = worker.analyze_page(image, page_num=2, language_hints=("en",), cancellation=token)
    assert result.cancelled
    assert worker._process is None


def test_worker_recovers_after_child_crash():
    worker = OcrWorker(False)
    with Image.new("RGB", (200, 100), "white") as image:
        try:
            worker.analyze_page(image, page_num=1, language_hints=("en",), cancellation=None)
            worker._process.kill()
            worker._process.join()
            with pytest.raises((EOFError, OSError, RuntimeError)):
                worker.analyze_page(image, page_num=2, language_hints=("en",), cancellation=None)
            assert worker._process is None
            result = worker.analyze_page(image, page_num=3, language_hints=("en",), cancellation=None)
            assert not result.cancelled
        finally:
            worker.close()
