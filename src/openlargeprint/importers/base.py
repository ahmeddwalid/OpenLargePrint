"""Base importer contract (DOC-001)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional
from openlargeprint.ir.models import DocumentIR, PageClassification
from openlargeprint.security.isolation import JobWorkspace

ProgressCallback = Callable[[int, int, str, str], None]  # (current_page, total_pages, stage, message)
CancelCheck = Callable[[], bool]
CheckpointCallback = Callable[[int, PageClassification, bool, Optional[str]], None]


class BaseImporter(ABC):
    """Abstract base class for all document importers normalizing into DocumentIR."""

    @abstractmethod
    def import_document(
        self,
        file_path: Path,
        workspace: JobWorkspace,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
        checkpoint_callback: Optional[CheckpointCallback] = None,
    ) -> DocumentIR:
        """Parse input document and return canonical DocumentIR."""
        pass
