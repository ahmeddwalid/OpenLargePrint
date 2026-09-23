from __future__ import annotations

import multiprocessing
import time
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from multiprocessing.util import Finalize
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from .base import CancellationToken, EnginePageResult

OCR_PAGE_TIMEOUT_SECONDS = 120.0
POLL_INTERVAL_SECONDS = 0.1
SHUTDOWN_TIMEOUT_SECONDS = 2.0


def _stop_worker(process: BaseProcess, sender: Connection, receiver: Connection) -> None:
    sender.close()
    receiver.close()
    if process.is_alive():
        process.terminate()
    process.join(SHUTDOWN_TIMEOUT_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(SHUTDOWN_TIMEOUT_SECONDS)
    process.close()


def _recognize(receiver: Connection, sender: Connection, use_gpu: bool) -> None:
    from .paddle_engine import PaddleRapidOcrEngine

    engine = PaddleRapidOcrEngine(use_gpu=use_gpu)
    try:
        while True:
            try:
                image_path, page_num, language_hints = receiver.recv()
            except EOFError:
                return
            try:
                with Image.open(image_path) as image:
                    result = engine._analyze_page(
                        image, page_num=page_num, language_hints=language_hints
                    )
                sender.send(result)
            except Exception:
                sender.send(None)
    finally:
        receiver.close()
        sender.close()


class OcrWorker:
    def __init__(self, use_gpu: bool, timeout_seconds: float = OCR_PAGE_TIMEOUT_SECONDS):
        self.use_gpu = use_gpu
        self.timeout_seconds = timeout_seconds
        self._process: BaseProcess | None = None
        self._connection: Connection | None = None
        self._sender: Connection | None = None
        self._finalizer: Finalize | None = None

    def close(self) -> None:
        if self._finalizer is not None:
            self._finalizer()
        self._process = None
        self._connection = None
        self._sender = None
        self._finalizer = None

    def analyze_page(
        self,
        image: Image.Image,
        *,
        page_num: int,
        language_hints: tuple[str, ...],
        cancellation: CancellationToken | None,
    ) -> EnginePageResult:
        if cancellation is not None and cancellation.is_cancelled():
            return EnginePageResult(lines=[], cancelled=True)
        if self._process is None:
            context = multiprocessing.get_context("spawn")
            child_reader, parent_writer = context.Pipe(duplex=False)
            parent_reader, child_writer = context.Pipe(duplex=False)
            process = context.Process(target=_recognize, args=(child_reader, child_writer, self.use_gpu), daemon=True)
            try:
                process.start()
            except BaseException:
                for endpoint in (child_reader, parent_writer, parent_reader, child_writer):
                    endpoint.close()
                raise
            child_reader.close()
            child_writer.close()
            self._process = process
            self._connection = parent_reader
            self._sender = parent_writer
            self._finalizer = Finalize(self, _stop_worker, args=(process, parent_writer, parent_reader), exitpriority=10)
        connection = self._connection
        assert connection is not None
        try:
            with TemporaryDirectory(prefix="olp-ocr-") as directory:
                image_path = Path(directory) / "page.png"
                image.save(image_path, format="PNG")
                deadline = time.monotonic() + self.timeout_seconds
                assert self._sender is not None
                self._sender.send((str(image_path), page_num, language_hints))
                while True:
                    if cancellation is not None and cancellation.is_cancelled():
                        self.close()
                        return EnginePageResult(lines=[], cancelled=True)
                    if time.monotonic() >= deadline:
                        self.close()
                        raise TimeoutError(f"Recognition took too long on page {page_num}. The original page is retained for review.")
                    if connection.poll(POLL_INTERVAL_SECONDS):
                        result = connection.recv()
                        if not isinstance(result, EnginePageResult):
                            raise RuntimeError(f"Recognition failed on page {page_num}. The original page is retained for review.")
                        return result
        except BaseException:
            self.close()
            raise
