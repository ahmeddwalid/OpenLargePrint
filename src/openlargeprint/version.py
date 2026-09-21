"""Single source of truth for the engine version.

Keep this in sync with `pyproject.toml` and `src-tauri/tauri.conf.json`; the
release pipeline derives artifact names from `tauri.conf.json`.
"""

from __future__ import annotations

__version__ = "0.1.0"
