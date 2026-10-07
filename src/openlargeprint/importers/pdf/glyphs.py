"""Symbol-font glyphs and private-use characters (PDF-002).

Dingbat fonts (Wingdings, Zapf Dingbats, Symbol) and many textbook fonts put
checkboxes, bullets and arrows in the Unicode private-use area. Left alone they
show up as empty boxes or vanish in the large-print font. Each is mapped to the
standard character with the same meaning; anything unknown becomes a visible
bullet so the reader can still see that a marker was there.
"""

from __future__ import annotations

from typing import Optional

# Wingdings / Wingdings 2 / Zapf Dingbats code points as they arrive through
# the PDF (either raw ASCII positions or remapped into U+F0xx).
_WINGDINGS = {
    0x6C: "●",  # l  black circle
    0x6D: "❍",  # m  shadowed circle
    0x6E: "■",  # n  black square
    0x6F: "□",  # o  white square
    0x70: "□",  # p
    0x71: "❑",  # q  checkbox
    0x72: "❒",  # r
    0x73: "◆",  # s
    0x74: "◆",  # t  diamond
    0x75: "◆",  # u
    0x76: "❖",  # v
    0x77: "◆",  # w
    0x9F: "•",
    0xA7: "▪",  # small square
    0xA8: "◻",
    0xD8: "➢",  # arrowhead
    0xDF: "←",
    0xE0: "→",
    0xE8: "➔",
    0xF0: "⇨",
    0xFB: "✗",  # ballot x
    0xFC: "✓",  # check mark
    0xFD: "☒",
    0xFE: "☑",
}

_ZAPF = {
    0x6C: "●", 0x6E: "■", 0x6F: "❏", 0x70: "❐", 0x71: "❑",
    0x72: "❒", 0x75: "◆", 0x76: "❖", 0x33: "✓", 0x34: "✔",
    0x37: "✗", 0x38: "✘", 0xA8: "♣", 0xAA: "♥", 0xD5: "→",
}

_SYMBOL = {0xB7: "•", 0xAE: "→", 0xAC: "←", 0xD7: "×", 0xB4: "×"}


def map_symbol_char(ch: str, font_name: str = "") -> Optional[str]:
    """Return a standard replacement for a dingbat or private-use glyph, else ``None``."""
    code = ord(ch)
    name = (font_name or "").lower()
    low = code - 0xF000 if 0xF000 <= code <= 0xF0FF else code
    if "wingding" in name or "webding" in name:
        return _WINGDINGS.get(low, "•" if code >= 0xE000 else None)
    if "zapf" in name or "dingbat" in name:
        return _ZAPF.get(low, "•" if code >= 0xE000 else None)
    if name.endswith("symbol") or "+symbol" in name:
        if 0xF000 <= code <= 0xF0FF:
            return _SYMBOL.get(low)
        return None
    if 0xE000 <= code <= 0xF8FF:
        return "•"
    return None


def clean_recognized_text(text: str) -> str:
    """Map private-use glyphs a recogniser emits (usually checkbox bullets)."""
    if not any(0xE000 <= ord(c) <= 0xF8FF for c in text):
        return text
    return "".join(map_symbol_char(c) or c for c in text)
