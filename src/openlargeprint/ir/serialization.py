"""Serialization and deserialization for DocumentIR (DOC-003)."""

from __future__ import annotations

import json
from typing import Any
from .models import DocumentIR


def document_to_json(doc: DocumentIR, indent: int = 2) -> str:
    """Serialize DocumentIR to a formatted JSON string."""
    return doc.model_dump_json(indent=indent)


def document_from_json(json_str: str) -> DocumentIR:
    """Deserialize DocumentIR from a JSON string with strict validation."""
    return DocumentIR.model_validate_json(json_str)


def document_to_dict(doc: DocumentIR) -> dict[str, Any]:
    """Export DocumentIR as a native Python dictionary."""
    return doc.model_dump()


def document_from_dict(data: dict[str, Any]) -> DocumentIR:
    """Instantiate DocumentIR from a Python dictionary."""
    return DocumentIR.model_validate(data)
