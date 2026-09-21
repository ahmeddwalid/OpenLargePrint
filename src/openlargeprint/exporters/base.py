"""Base exporter contract and preset definitions (DOC-001, OUT-001, OUT-006, OUT-007)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import math
from typing import Optional
from openlargeprint.ir.models import DocumentIR


class PaperSize(str, Enum):
    """Supported print-ready paper sizes (OUT-007)."""
    A4 = "A4"  # Default (210 x 297 mm)
    A3 = "A3"  # First-class alternate (297 x 420 mm)


class PresetName(str, Enum):
    """Text-size presets defined in OUT-006."""
    COMFORTABLE = "Comfortable"    # 18pt / 1.4
    LARGE = "Large"                # 20pt / 1.5 (default)
    EXTRA_LARGE = "Extra Large"    # 24pt / 1.5
    VERY_LARGE = "Very Large"      # 28pt / 1.55
    CUSTOM = "Custom"


@dataclass
class PresetConfig:
    body_pt: float
    line_spacing: float
    description: str


PRESET_CONFIGS = {
    PresetName.COMFORTABLE: PresetConfig(18.0, 1.4, "Comfortable (18pt, 1.4 spacing)"),
    PresetName.LARGE: PresetConfig(20.0, 1.5, "Large - Default (20pt, 1.5 spacing)"),
    PresetName.EXTRA_LARGE: PresetConfig(24.0, 1.5, "Extra Large (24pt, 1.5 spacing)"),
    PresetName.VERY_LARGE: PresetConfig(28.0, 1.55, "Very Large (28pt, 1.55 spacing)"),
}

MIN_BODY_PT = 12.0
MAX_BODY_PT = 72.0
MIN_LINE_SPACING = 1.0
MAX_LINE_SPACING = 3.0


@dataclass
class ExportOptions:
    """Options governing document reflow and large-print rendering."""
    preset: PresetName = PresetName.LARGE
    paper_size: PaperSize = PaperSize.A4
    include_page_markers: bool = True
    font_family: str = "Atkinson Hyperlegible"
    fallback_font: str = "Arial"
    custom_body_pt: Optional[float] = None
    custom_line_spacing: Optional[float] = None
    monochrome: bool = False

    def __post_init__(self) -> None:
        self.preset = PresetName(self.preset)
        self.paper_size = PaperSize(self.paper_size)
        if self.preset == PresetName.CUSTOM:
            if self.custom_body_pt is None:
                self.custom_body_pt = PRESET_CONFIGS[PresetName.LARGE].body_pt
            if self.custom_line_spacing is None:
                self.custom_line_spacing = PRESET_CONFIGS[PresetName.LARGE].line_spacing
        for value, lower, upper, label in (
            (self.custom_body_pt, MIN_BODY_PT, MAX_BODY_PT, "Text size"),
            (self.custom_line_spacing, MIN_LINE_SPACING, MAX_LINE_SPACING, "Line spacing"),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not lower <= value <= upper
            ):
                raise ValueError(f"{label} must be between {lower:g} and {upper:g}.")

    @property
    def body_pt(self) -> float:
        if self.preset == PresetName.CUSTOM and self.custom_body_pt is not None:
            return self.custom_body_pt
        return PRESET_CONFIGS[self.preset].body_pt

    @property
    def line_spacing(self) -> float:
        if self.preset == PresetName.CUSTOM and self.custom_line_spacing is not None:
            return self.custom_line_spacing
        return PRESET_CONFIGS[self.preset].line_spacing


class BaseExporter(ABC):
    """Abstract base class for all document exporters reading from DocumentIR."""

    @abstractmethod
    def export(self, doc: DocumentIR, output_path: Path, options: ExportOptions) -> Path:
        """Render DocumentIR into target format."""
        pass
