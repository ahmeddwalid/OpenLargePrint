"""Base importer contract (DOC-001)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from openlargeprint.ir.models import DocumentIR
from openlargeprint.security.isolation import JobWorkspace


class BaseImporter(ABC):
    """Abstract base class for all document importers normalizing into DocumentIR."""

    @abstractmethod
    def import_document(self, file_path: Path, workspace: JobWorkspace) -> DocumentIR:
        """Parse input document and return canonical DocumentIR."""
        pass
