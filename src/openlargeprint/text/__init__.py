"""Text processing, script detection, and bidirectional shaping utilities (LANG-001, LANG-002)."""

from .direction import (
    detect_language,
    detect_text_direction,
    is_arabic_char,
    is_bidi_text,
    is_rtl_char,
    normalize_arabic_logical_order,
)
from .bidi import reorder_bidi_for_display

__all__ = [
    "detect_language",
    "detect_text_direction",
    "is_arabic_char",
    "is_bidi_text",
    "is_rtl_char",
    "normalize_arabic_logical_order",
    "reorder_bidi_for_display",
]
