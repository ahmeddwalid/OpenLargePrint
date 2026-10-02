"""Actual optional runtime must recognize locally without network (SEC-009)."""
import socket
import urllib.request

import pytest
from PIL import Image, ImageDraw, ImageFont

from openlargeprint.ocr.router import OcrRouter


@pytest.mark.skipif(OcrRouter._modern_model_path("en") is None, reason="Verified optional English accuracy pack is not installed")
def test_actual_accuracy_initialization_and_recognition_are_offline(monkeypatch):
    import requests
    from openlargeprint.ocr.modern_engine import ModernRapidOcrEngine
    def deny(*args, **kwargs):
        raise AssertionError("Recognition attempted network access")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(urllib.request, "urlopen", deny)
    monkeypatch.setattr(requests.Session, "request", deny)
    page = Image.new("RGB", (650, 130), "white")
    ImageDraw.Draw(page).text((30, 35), "Judicial Review", font=ImageFont.load_default(size=38), fill="black")
    engine = ModernRapidOcrEngine(str(OcrRouter._modern_model_path("en")))
    try:
        result = engine._analyze_page(page, page_num=1)
        assert "Judicial Review" in " ".join(line.text for line in result.lines)
    finally:
        engine.close()


def test_worker_network_guard_rejects_connection_and_name_resolution():
    from openlargeprint.ocr.worker import _deny_worker_network
    for event in ("socket.connect", "socket.getaddrinfo", "urllib.Request"):
        with pytest.raises(PermissionError, match="offline"):
            _deny_worker_network(event, ())
    _deny_worker_network("open", ("local-model.onnx",))
