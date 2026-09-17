"""Content-based file type and resource limits validation (SEC-001, SEC-003)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

# Maximum allowed input file size (default: 500 MB)
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

# Maximum allowed image dimension in pixels (SEC-003)
MAX_IMAGE_DIMENSION = 10000
MAX_IMAGE_PIXELS = 50_000_000  # 50 MP limit (allows 10000x5000 banners, but caps total raster size)


class SecurityValidationError(ValueError):
    """Raised when an input file fails security or resource limit checks."""
    pass


SupportedFormat = Literal["pdf", "docx", "pptx"]


def detect_file_type(path: str | Path) -> SupportedFormat:
    """Validate file type by sniffing content magic bytes, NOT by file extension (SEC-001)."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {file_path}")

    if not file_path.is_file():
        raise SecurityValidationError(f"Input path is not a regular file: {file_path}")

    # Check file size (SEC-003)
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise SecurityValidationError("The file is empty.")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise SecurityValidationError(
            f"File exceeds maximum allowed size ({file_size / (1024*1024):.1f} MB > {MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB)."
        )

    # Read the first 2048 bytes for magic number analysis
    with open(file_path, "rb") as f:
        header = f.read(2048)

    # Check PDF magic bytes (%PDF-) anywhere in first 1024 bytes (per PDF spec)
    if b"%PDF-" in header[:1024]:
        return "pdf"

    # Check ZIP / OOXML magic bytes (PK\x03\x04)
    if header.startswith(b"PK\x03\x04"):
        return "docx"

    raise SecurityValidationError(
        "File format not recognized or supported. The file must be a genuine PDF or modern Office document."
    )


def validate_image_dimensions(width: int, height: int) -> None:
    """Enforce bounds on image raster dimensions (SEC-003)."""
    if width <= 0 or height <= 0:
        raise SecurityValidationError(f"Invalid image dimensions: {width}x{height}")

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise SecurityValidationError(
            f"Image dimensions {width}x{height} exceed safety limit of {MAX_IMAGE_DIMENSION}px"
        )

    total_pixels = width * height
    if total_pixels > MAX_IMAGE_PIXELS:
        raise SecurityValidationError(
            f"Image total pixels ({total_pixels}) exceed safety limit of {MAX_IMAGE_PIXELS}"
        )
