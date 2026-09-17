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


import zipfile

SupportedFormat = Literal["pdf", "docx", "pptx", "doc", "ppt"]

# OLE2 Compound File Binary Format magic bytes (D0 CF 11 E0 A1 B1 1A E1)
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# UTF-16LE stream names embedded in OLE2 directory entries
OLE2_WORD_STREAM = "WordDocument".encode("utf-16le")
OLE2_PPT_STREAM_1 = "PowerPoint Document".encode("utf-16le")
OLE2_PPT_STREAM_2 = "Current User".encode("utf-16le")


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

    # Read the first 4096 bytes for magic number analysis
    with open(file_path, "rb") as f:
        header = f.read(4096)

    # 1. Check PDF magic bytes (%PDF-) anywhere in first 1024 bytes (per PDF spec)
    if b"%PDF-" in header[:1024]:
        return "pdf"

    # 2. Check ZIP / OpenXML magic bytes (PK\x03\x04)
    if header.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = set(zf.namelist())
                # Check for Word OpenXML signatures
                if any(n.startswith("word/") for n in names) or "word/document.xml" in names:
                    return "docx"
                # Check for PowerPoint OpenXML signatures
                if any(n.startswith("ppt/") for n in names) or "ppt/presentation.xml" in names:
                    return "pptx"
                raise SecurityValidationError(
                    "ZIP archive does not contain a valid Word (word/) or PowerPoint (ppt/) structure."
                )
        except zipfile.BadZipFile:
            raise SecurityValidationError("Corrupted or invalid OpenXML ZIP archive.")

    # 3. Check legacy OLE2 binary format (DOC / PPT)
    if header.startswith(OLE2_MAGIC):
        # Scan header and subsequent chunks for Word vs PowerPoint stream directory entries
        with open(file_path, "rb") as f:
            ole_data = f.read(min(file_size, 512 * 1024))  # Scan first 512KB for directory stream names

        if OLE2_WORD_STREAM in ole_data:
            return "doc"
        if OLE2_PPT_STREAM_1 in ole_data or OLE2_PPT_STREAM_2 in ole_data:
            return "ppt"

        raise SecurityValidationError(
            "Legacy OLE2 compound file is not a supported Word (.doc) or PowerPoint (.ppt) document."
        )

    raise SecurityValidationError(
        "File format not recognized or supported. The file must be a genuine PDF, DOCX, PPTX, DOC, or PPT document."
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
