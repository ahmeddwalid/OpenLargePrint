"""Content-based file type and resource limits validation (SEC-001, SEC-003)."""

from __future__ import annotations

import math
import shutil
import zipfile
from pathlib import Path
from typing import Literal

# Maximum allowed input file size (default: 500 MB)
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

# Maximum allowed image dimension in pixels (SEC-003)
MAX_IMAGE_DIMENSION = 10000
MAX_IMAGE_PIXELS = 50_000_000  # 50 MP limit (allows 10000x5000 banners, but caps total raster size)
MAX_RENDER_PIXELS = 16_000_000


def bounded_pdf_scale(width: float, height: float, dpi: float = 300.0) -> float:
    if any(not math.isfinite(v) or v <= 0 for v in (width, height, dpi)):
        raise SecurityValidationError("The page dimensions or resolution are invalid.")
    scale = min(
        dpi / 72.0,
        (MAX_IMAGE_DIMENSION - 1) / width,
        (MAX_IMAGE_DIMENSION - 1) / height,
        math.sqrt(MAX_RENDER_PIXELS / width / height) * 0.99,
    )
    validate_image_dimensions(math.ceil(width * scale), math.ceil(height * scale))
    return scale


class SecurityValidationError(ValueError):
    """Raised when an input file fails security or resource limit checks."""
    pass



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




def safe_extract_zip(
    zip_path: str | Path,
    dest_dir: str | Path,
    max_uncompressed_bytes: int = MAX_FILE_SIZE_BYTES,
    max_ratio: float = 100.0,
) -> list[Path]:
    """Safely extract ZIP archive members with zip-slip and zip-bomb prevention (SEC-003)."""
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    extracted_paths: list[Path] = []

    total_uncompressed = 0
    total_compressed = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            # Check for zip-slip (path traversal attempt)
            member_path = (dest / info.filename).resolve()
            try:
                member_path.relative_to(dest)
            except ValueError:
                raise SecurityValidationError(
                    f"Zip-slip path traversal attempt detected in archive member: {info.filename}"
                )

            # Check for zip bomb
            total_uncompressed += info.file_size
            total_compressed += info.compress_size

            if total_uncompressed > max_uncompressed_bytes:
                raise SecurityValidationError(
                    f"Decompressed archive size exceeds safety limit ({total_uncompressed} > {max_uncompressed_bytes} bytes)."
                )

            if total_compressed > 0:
                ratio = total_uncompressed / total_compressed
                if ratio > max_ratio and total_uncompressed > 10 * 1024 * 1024:
                    raise SecurityValidationError(
                        f"Decompression bomb detected: expansion ratio {ratio:.1f} exceeds safety threshold of {max_ratio}."
                    )

            if info.is_dir():
                member_path.mkdir(parents=True, exist_ok=True)
            else:
                member_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(member_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_paths.append(member_path)

    return extracted_paths
