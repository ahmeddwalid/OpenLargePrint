"""Content-free job heartbeat, stopped before terminal events (UI-002, SEC-007)."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .protocol import ProgressEvent


class JobProgress:
    def __init__(self, job_id: str, emit: Callable, interval: float = 2.0):
        self.job_id = job_id
        self.emit = emit
        self.interval = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._state = (0, 1, "preparing", "Preparing document")
        self._started = time.monotonic()
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)

    def __enter__(self):
        self._publish()
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join()

    def update(self, current: int, total: int, stage: str, message: str):
        with self._lock:
            self._state = (current, total, stage, message)
            self._publish_locked()

    def _publish(self):
        with self._lock:
            self._publish_locked()

    def _publish_locked(self):
        current, total, stage, message = self._state
        percent = 95.0 if stage == "exporting" else min(90.0, current / max(1, total) * 90)
        self.emit(ProgressEvent(job_id=self.job_id, stage=stage, current_page=current,
                               total_pages=total, percent=round(percent, 1), message=message,
                               elapsed_seconds=round(time.monotonic() - self._started, 3)))

    def _heartbeat(self):
        while not self._stop.wait(self.interval):
            self._publish()
