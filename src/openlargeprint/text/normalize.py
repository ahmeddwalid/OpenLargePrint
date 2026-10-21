"""Fold Arabic presentation forms back into ordinary letters.

Older PDFs and some fonts store Arabic as presentation forms (U+FB50-U+FDFF,
U+FE70-U+FEFF): one code point per positional shape, and one for ligatures
such as lam-alef. They look right but search, copy, screen readers and our own
shaping all expect the base letters. Compatibility decomposition gives those
back in reading order ("ﻻ" becomes "لا"). Only these two blocks are folded so
that other compatibility characters (superscripts, full-width forms) are left
alone.
"""

from __future__ import annotations

import unicodedata


def is_presentation_form(ch: str) -> bool:
    code = ord(ch)
    return 0xFB50 <= code <= 0xFDFF or 0xFE70 <= code <= 0xFEFF


def fold_presentation_forms(text: str) -> str:
    if not any(is_presentation_form(ch) for ch in text):
        return text
    folded = "".join(unicodedata.normalize("NFKC", ch) if is_presentation_form(ch) else ch for ch in text)
    return unicodedata.normalize("NFC", folded)
