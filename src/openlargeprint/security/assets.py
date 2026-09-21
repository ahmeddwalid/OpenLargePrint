"""Persistent per-job asset storage (IMG-001, SEC-004).

Extracted images and retained source-region crops must remain readable after the
disposable :class:`JobWorkspace` is torn down, so the desktop UI and re-export
paths can still render them. This module keeps those media files in a stable,
per-job directory while the scratch space used for parsing stays isolated and
disposable (SEC-004).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Optional


def default_cache_root() -> Path:
    """Resolve a platform-appropriate persistent cache root."""
    override = os.environ.get("OPENLARGEPRINT_CACHE_DIR")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "OpenLargePrint"
        return Path.home() / "AppData" / "Local" / "OpenLargePrint"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "OpenLargePrint"

    xdg = os.environ.get("XDG_CACHE_HOME")
    base_path = Path(xdg) if xdg else Path.home() / ".cache"
    return base_path / "openlargeprint"


class JobAssetStore:
    """Owns the persistent asset directory for a single conversion job."""

    def __init__(
        self,
        job_id: Optional[str] = None,
        root: Optional[str | Path] = None,
    ):
        self.job_id = job_id or f"job-{uuid.uuid4().hex[:12]}"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", self.job_id):
            raise ValueError("Invalid conversion job identifier.")
        self.root = Path(root) if root else default_cache_root()
        self.jobs_dir = self.root / "jobs"
        self.job_dir = self.jobs_dir / self.job_id
        self.assets_dir = self.job_dir / "assets"

    def ensure(self) -> Path:
        """Create and return the job's asset directory."""
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        return self.assets_dir

    def prune(self, max_age_days: int = 14, max_jobs: int = 50) -> int:
        """Delete stale job directories, keeping the newest ``max_jobs``.

        Returns the number of job directories removed. Failures are ignored so
        pruning can never break a conversion.
        """
        if not self.jobs_dir.exists():
            return 0

        try:
            entries = [p for p in self.jobs_dir.iterdir() if p.is_dir() and not p.is_symlink()]
        except OSError:
            return 0

        def _mtime(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:
                return 0.0

        entries.sort(key=_mtime, reverse=True)
        cutoff = time.time() - max_age_days * 86400
        removed = 0

        for index, entry in enumerate(entries):
            if entry == self.job_dir:
                continue
            too_old = _mtime(entry) < cutoff
            beyond_limit = index >= max_jobs
            if too_old or beyond_limit:
                try:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
                except OSError:
                    continue

        return removed
