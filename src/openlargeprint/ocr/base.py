"""OCR engine protocol and shared result representations (OCR-001, OCR-004)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, Tuple, runtime_checkable
from PIL import Image


@dataclass
class EngineCapabilities:
    """Declared capabilities of an OCR engine adapter (OCR-001)."""
    engine_name: str
    supports_layout: bool
    supports_confidence: bool
    supported_languages: List[str]
    is_gpu_accelerated: bool = False


@dataclass
class OcrDetectedLine:
    """Single line of recognized text with pixel-space geometry and confidence."""
    text: str
    polygon: List[Tuple[float, float]]  # List of 4 (x, y) vertices in image pixels
    confidence: float

    @property
    def x0(self) -> float:
        return min(p[0] for p in self.polygon)

    @property
    def y0(self) -> float:
        return min(p[1] for p in self.polygon)

    @property
    def x1(self) -> float:
        return max(p[0] for p in self.polygon)

    @property
    def y1(self) -> float:
        return max(p[1] for p in self.polygon)

    @property
    def width(self) -> float:
        return abs(self.x1 - self.x0)

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


@dataclass
class EnginePageResult:
    """Result of running an OCR engine over a rendered page image."""
    lines: List[OcrDetectedLine]
    elapse_seconds: float = 0.0
    warnings: List[str] = field(default_factory=list)
    cancelled: bool = False


class CancellationToken:
    """Cooperative cancellation flag for long OCR work (UI-002, DESIGN.md §4)."""

    def __init__(self, check: Callable[[], bool] | None = None):
        self._cancelled = False
        self._check = check

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled or (self._check is not None and self._check())

    def __bool__(self) -> bool:
        return self.is_cancelled()


@runtime_checkable
class DocumentOcrEngine(Protocol):
    """Abstract interface for all swappable OCR engines (OCR-001)."""

    def capabilities(self) -> EngineCapabilities:
        """Return engine capabilities and constraints."""
        ...

    def analyze_page(
        self,
        image: Image.Image,
        *,
        page_num: int,
        language_hints: Tuple[str, ...] = ("en",),
        cancellation: Optional[CancellationToken] = None,
    ) -> EnginePageResult:
        """Run text recognition on a rendered page image."""
        ...
