"""Security and resource bounding package (SEC-001..009)."""

from .validator import (
    SecurityValidationError,
    SupportedFormat,
    detect_file_type,
    safe_extract_zip,
    validate_image_dimensions,
)
from .isolation import JobWorkspace, log_safe_info
from .assets import JobAssetStore, default_cache_root
from .sanitizer import (
    ActiveContentStrippedWarning,
    sanitize_document,
    sanitize_office_openxml,
    sanitize_pdf,
)

__all__ = [
    "ActiveContentStrippedWarning",
    "JobAssetStore",
    "JobWorkspace",
    "default_cache_root",
    "SecurityValidationError",
    "SupportedFormat",
    "detect_file_type",
    "log_safe_info",
    "safe_extract_zip",
    "sanitize_document",
    "sanitize_office_openxml",
    "sanitize_pdf",
    "validate_image_dimensions",
]

