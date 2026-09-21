"""Disposable job workspace and privacy-safe logging (SEC-004, SEC-007)."""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Optional

if TYPE_CHECKING:
    from .assets import JobAssetStore


logger = logging.getLogger("openlargeprint")


@contextmanager
def atomic_output(output_path: Path) -> Generator[Path, None, None]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".olp-export-", suffix=output_path.suffix, dir=output_path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        yield temporary
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise OSError("The export did not produce a complete file.")
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)


class JobWorkspace:
    """Disposable, isolated working directory for a conversion job (SEC-004).

    The scratch directory is always disposable. When an ``asset_store`` is
    supplied, extracted media is written there instead of into the scratch
    directory, so it survives teardown and remains addressable by the UI and
    re-export paths (IMG-001).
    """

    def __init__(
        self,
        base_dir: Optional[str | Path] = None,
        prefix: str = "olp-job-",
        asset_store: Optional["JobAssetStore"] = None,
    ):
        self.base_dir = Path(base_dir) if base_dir else None
        self.prefix = prefix
        self.asset_store = asset_store
        self._temp_dir: Optional[tempfile.TemporaryDirectory[str]] = None
        self.path: Optional[Path] = None
        self.assets_dir: Optional[Path] = None

    def __enter__(self) -> "JobWorkspace":
        self._temp_dir = tempfile.TemporaryDirectory(
            prefix=self.prefix,
            dir=self.base_dir,
        )
        self.path = Path(self._temp_dir.name)
        if self.asset_store is not None:
            # Persistent media directory outside the disposable scratch space.
            self.assets_dir = self.asset_store.ensure()
        else:
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
