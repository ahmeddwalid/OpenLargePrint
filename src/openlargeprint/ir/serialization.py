"""Serialization and deserialization for DocumentIR (DOC-003)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from .models import DocumentIR


def document_to_json(doc: DocumentIR, indent: int = 2) -> str:
    """Serialize DocumentIR to a formatted JSON string."""
    return doc.model_dump_json(indent=indent)


def document_to_ui_dict(
    doc: DocumentIR,
    embed_assets: bool = True,
    max_asset_bytes: int = 8 * 1024 * 1024,
) -> dict[str, Any]:
    """Export DocumentIR as a dict enriched for the desktop UI (IMG-001).

    Each IMAGE/TABLE block's ``image_asset`` gains a base64 ``data_url`` so the
    webview can render it directly (the Tauri CSP permits ``data:`` images, and
    the UI needs no filesystem asset protocol — SEC-005). Assets larger than
    ``max_asset_bytes`` keep only their ``file_path``.
    """
    data = document_to_dict(doc)
    if not embed_assets:
        return data

    for block in data.get("blocks", []):
        asset = block.get("image_asset")
        if not isinstance(asset, dict):
            continue
        raw_path = asset.get("file_path")
        if not raw_path:
            continue
        path = Path(raw_path)
        try:
            if not path.exists() or path.stat().st_size > max_asset_bytes:
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        mime = asset.get("mime_type") or "image/png"
        asset["data_url"] = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    return data


def document_from_json(json_str: str) -> DocumentIR:
    """Deserialize DocumentIR from a JSON string with strict validation."""
    return DocumentIR.model_validate_json(json_str)


def document_to_dict(doc: DocumentIR) -> dict[str, Any]:
    """Export DocumentIR as a native Python dictionary."""
    return doc.model_dump()


def document_from_dict(data: dict[str, Any]) -> DocumentIR:
    """Instantiate DocumentIR from a Python dictionary."""
    return DocumentIR.model_validate(data)
