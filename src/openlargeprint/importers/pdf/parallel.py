"""Convert the pages of a PDF side by side in worker processes (PERF-001).

Each worker opens the PDF itself, loads the layout model and the recognisers
once, and converts the pages it is given. Workers block every network call
(SEC-008, SEC-009) and split the CPU cores between them. Results come back in
page order whatever order the pages finish in, so the document is assembled
exactly as a one-page-at-a-time conversion would assemble it.

If a worker dies (for example when the computer runs out of memory) its page
is handed back to the caller to convert in the main process, and the rest of
the document carries on.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import get_context
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Iterator, List, Optional, Tuple

from openlargeprint import runtime
from openlargeprint.security.isolation import log_safe_info

POLL_SECONDS = 0.2

_worker: Dict[str, object] = {}


def _deny_network(event: str, args: tuple) -> None:
    if event in ("socket.connect", "socket.getaddrinfo", "urllib.Request"):
        raise PermissionError("Conversion runs offline.")


def _start_worker(pdf_path: str, assets_dir: str, scratch_dir: str, routing_mode: str, ocr_dpi: float,
                  language: str) -> None:
    sys.addaudithook(_deny_network)
    import pypdfium2 as pdfium

    from openlargeprint.layout.detector import get_layout_detector
    from openlargeprint.ocr.router import RoutingMode
    from .native import NativePdfImporter

    importer = NativePdfImporter(routing_mode=RoutingMode(routing_mode), ocr_dpi=ocr_dpi)
    importer._router = type(importer._router)(in_process=True)
    _worker.update(
        importer=importer,
        pdf=pdfium.PdfDocument(pdf_path),
        layout=get_layout_detector(),
        workspace=SimpleNamespace(assets_dir=Path(assets_dir), path=Path(scratch_dir)),
        language=language,
    )


def _convert(index: int, page_count: int):
    from .native import next_language

    importer = _worker["importer"]
    outcome = importer.convert_page(_worker["pdf"], index, page_count, _worker["workspace"],
                                    _worker["layout"], _worker["language"], None, None)
    # What one page shows about the document's script helps this worker's next pages.
    _worker["language"] = next_language(_worker["language"], outcome.blocks)
    return outcome


class PagePool:
    def __init__(self, pdf_path: Path, page_count: int, workspace, routing_mode, ocr_dpi: float,
                 workers: int, threads: int, language: str):
        runtime.settle_gpu()  # decided once here; the workers inherit the answer
        saved = {name: os.environ.get(name) for name in ("OLP_ONNX_THREADS",)}
        os.environ["OLP_ONNX_THREADS"] = str(threads)
        try:
            self._executor = ProcessPoolExecutor(
                max_workers=workers,
                mp_context=get_context("spawn"),
                initializer=_start_worker,
                initargs=(str(pdf_path), str(workspace.assets_dir), str(workspace.path),
                          getattr(routing_mode, "value", str(routing_mode)), float(ocr_dpi), language),
            )
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        self._workers = workers
        self._page_count = page_count

    def run(self, indices: List[int], cancel_check=None) -> Iterator[Tuple[int, Optional[object]]]:
        """Yield (page index, outcome) in page order; outcome None means "convert it yourself"."""
        pending: Dict[Future, int] = {}
        queue = list(indices)
        done: Dict[int, Optional[object]] = {}
        broken = False
        # A few pages more than workers are queued so no worker waits.
        ahead = self._workers * 2

        def submit() -> None:
            nonlocal broken
            while queue and len(pending) < ahead and not broken:
                index = queue.pop(0)
                try:
                    pending[self._executor.submit(_convert, index, self._page_count)] = index
                except (BrokenProcessPool, RuntimeError):
                    broken = True
                    done[index] = None

        submit()
        for index in indices:
            while index not in done:
                if cancel_check and cancel_check():
                    raise InterruptedError("Operation cancelled by user.")
                if broken and index in queue:
                    queue.remove(index)
                    done[index] = None
                    break
                finished, _ = wait(list(pending), timeout=POLL_SECONDS, return_when=FIRST_COMPLETED)
                for future in finished:
                    page = pending.pop(future)
                    try:
                        done[page] = future.result()
                    except InterruptedError:
                        raise
                    except BrokenProcessPool:
                        broken = True
                        done[page] = None
                    except Exception as exc:
                        log_safe_info(f"Page {page + 1} failed in a worker ({type(exc).__name__})")
                        done[page] = None
                submit()
            yield index, done.pop(index)

    def close(self) -> None:
        # Cancelled or finished: stop at once rather than waiting for queued pages.
        processes = list(getattr(self._executor, "_processes", {}).values())
        self._executor.shutdown(wait=False, cancel_futures=True)
        deadline = time.monotonic() + 2.0
        for process in processes:
            process.join(max(0.0, deadline - time.monotonic()))
            if process.is_alive():
                process.terminate()
