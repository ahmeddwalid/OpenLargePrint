"""Fonts for the large-print outputs (OUT-001, OUT-003, LANG-001).

The output typeface is Atkinson Hyperlegible, designed by the Braille Institute
for readers with low vision: letters that are easy to confuse (I l 1, O 0, b d)
are drawn to stay distinct. It ships with the application, so every PDF and
Word document looks the same on every computer.

Atkinson covers Latin text but not phonetic symbols, arrows or check boxes,
which language books use constantly. Characters it lacks are set in DejaVu
Sans, and Arabic in Noto Sans Arabic, so nothing turns into an empty box.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
from xml.sax.saxutils import escape

from openlargeprint.security.isolation import log_safe_info

FONT_FAMILY = "Atkinson Hyperlegible"


def bundled_font_dir() -> Path:
    here = Path(__file__).resolve().parent / "fonts"
    if here.is_dir():
        return here
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "openlargeprint" / "exporters" / "fonts").is_dir():
        return Path(meipass) / "openlargeprint" / "exporters" / "fonts"
    return here


FONT_FILES = {
    "OLP-Regular": "AtkinsonHyperlegible-Regular.ttf",
    "OLP-Bold": "AtkinsonHyperlegible-Bold.ttf",
    "OLP-Italic": "AtkinsonHyperlegible-Italic.ttf",
    "OLP-BoldItalic": "AtkinsonHyperlegible-BoldItalic.ttf",
    "OLP-Fallback": "DejaVuSans.ttf",
    "OLP-FallbackBold": "DejaVuSans-Bold.ttf",
    "OLP-Arabic": "NotoSansArabic.ttf",
}


@dataclass(frozen=True)
class FontSet:
    regular: str
    bold: str
    italic: str
    bold_italic: str
    fallback: str
    fallback_bold: str
    arabic: str


_HELVETICA = FontSet("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
                     "Helvetica", "Helvetica-Bold", "Helvetica")


@lru_cache(maxsize=1)
def output_fonts() -> FontSet:
    """Register the bundled faces with ReportLab once per process."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    directory = bundled_font_dir()
    try:
        for name, filename in FONT_FILES.items():
            pdfmetrics.registerFont(TTFont(name, str(directory / filename)))
    except Exception as exc:
        log_safe_info(f"Bundled fonts unavailable ({type(exc).__name__}); using Helvetica")
        return _HELVETICA
    addMapping("OLP-Regular", 0, 0, "OLP-Regular")
    addMapping("OLP-Regular", 1, 0, "OLP-Bold")
    addMapping("OLP-Regular", 0, 1, "OLP-Italic")
    addMapping("OLP-Regular", 1, 1, "OLP-BoldItalic")
    addMapping("OLP-Fallback", 0, 0, "OLP-Fallback")
    addMapping("OLP-Fallback", 1, 0, "OLP-FallbackBold")
    addMapping("OLP-Fallback", 0, 1, "OLP-Fallback")
    addMapping("OLP-Fallback", 1, 1, "OLP-FallbackBold")
    return FontSet("OLP-Regular", "OLP-Bold", "OLP-Italic", "OLP-BoldItalic",
                   "OLP-Fallback", "OLP-FallbackBold", "OLP-Arabic")


@lru_cache(maxsize=8)
def _coverage(font_name: str) -> frozenset:
    from reportlab.pdfbase import pdfmetrics
    try:
        face = pdfmetrics.getFont(font_name).face
        return frozenset(face.charToGlyph.keys())
    except Exception:
        return frozenset()


def markup(text: str, fonts: Optional[FontSet] = None) -> str:
    """Escape text for a ReportLab paragraph, switching font for missing glyphs."""
    fonts = fonts or output_fonts()
    covered = _coverage(fonts.regular)
    if not covered:
        return escape(text)
    fallback = _coverage(fonts.fallback)
    out: List[str] = []
    run: List[str] = []
    run_is_fallback = False
    for ch in text:
        needs = ord(ch) > 0x7F and ord(ch) not in covered and not ch.isspace() and ord(ch) in fallback
        if needs != run_is_fallback and run:
            chunk = escape("".join(run))
            out.append(f'<font name="{fonts.fallback}">{chunk}</font>' if run_is_fallback else chunk)
            run = []
        run_is_fallback = needs
        run.append(ch)
    if run:
        chunk = escape("".join(run))
        out.append(f'<font name="{fonts.fallback}">{chunk}</font>' if run_is_fallback else chunk)
    return "".join(out)


def ensure_arabic_font() -> str:
    return output_fonts().arabic


def resolve_reportlab_family(family: str = FONT_FAMILY, fallback: str = "Arial") -> Dict[str, str]:
    fonts = output_fonts()
    return {"normal": fonts.regular, "bold": fonts.bold, "italic": fonts.italic, "boldItalic": fonts.bold_italic}


def css_font_stack(family: str = FONT_FAMILY, fallback: str = "Arial") -> str:
    parts = [f'"{family}"']
    if fallback and fallback.lower() != family.lower():
        parts.append(f'"{fallback}"')
    parts += ['"DejaVu Sans"', '"Segoe UI"', "Arial", "sans-serif"]
    return ", ".join(parts)
