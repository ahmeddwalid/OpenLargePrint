"""Disposable job workspace and privacy-safe logging (SEC-004, SEC-007)."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Optional


logger = logging.getLogger("openlargeprint")


class JobWorkspace:
    """Disposable, isolated working directory for a conversion job (SEC-004)."""

    def __init__(self, base_dir: Optional[str | Path] = None, prefix: str = "olp-job-"):
        self.base_dir = Path(base_dir) if base_dir else None
        self.prefix = prefix
        self._temp_dir: Optional[tempfile.TemporaryDirectory[str]] = None
        self.path: Optional[Path] = None
        self.assets_dir: Optional[Path] = None

    def __enter__(self) -> "JobWorkspace":
        self._temp_dir = tempfile.TemporaryDirectory(
            prefix=self.prefix,
            dir=self.base_dir,
        )
        self.path = Path(self._temp_dir.name)
        # Create dedicated assets directory
        self.assets_dir = self.path / "assets"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception as e:
                # Log without raising to prevent masking primary exceptions
                logger.warning(f"Error cleaning up temporary directory: {e}")
            self._temp_dir = None
            self.path = None
            self.assets_dir = None


def log_safe_info(message: str) -> None:
    """Log an operational event, strictly forbidding document text/content (SEC-007)."""
    # Defensive check against long strings that could be extracted text chunks
    if len(message) > 500:
        message = message[:200] + "... [truncated for privacy]"
    logger.info(message)
