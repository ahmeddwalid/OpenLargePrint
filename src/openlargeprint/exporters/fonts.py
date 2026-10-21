"""Fonts for the large-print outputs (OUT-001, OUT-003, LANG-001).

Readers pick the typeface they find easiest: one for Latin script and one for
Arabic. The default is Atkinson Hyperlegible, designed by the Braille Institute
for readers with low vision (letters that are easy to confuse, such as I l 1
and O 0, stay distinct), with Noto Sans Arabic for Arabic. Every choice ships
with the application under the SIL Open Font License, so a PDF or Word
document looks the same on every computer.

Characters a chosen font lacks (phonetic symbols, arrows, check boxes, or
Persian letters in an Arabic-only font) are set in DejaVu Sans, so nothing
turns into an empty box. scripts/prepare_fonts.py builds the font files.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from openlargeprint.security.isolation import log_safe_info

STYLES = ("Regular", "Bold", "Italic", "BoldItalic")


@dataclass(frozen=True)
class FontChoice:
    id: str
    family: str          # the name Word, browsers and the settings list show
    file_prefix: str     # <prefix>-<Style>.ttf in the fonts folder
    script: str          # "latin" or "arabic"
    styles: Tuple[str, ...] = ("Regular", "Bold")
    note: str = ""

    def file(self, style: str) -> str:
        """The file for a style, falling back to the nearest face that exists."""
        if style not in self.styles:
            style = "Bold" if "Bold" in style and "Bold" in self.styles else "Regular"
        return f"{self.file_prefix}-{style}.ttf"


LATIN_FONTS: Dict[str, FontChoice] = {f.id: f for f in (
    FontChoice("atkinson", "Atkinson Hyperlegible", "AtkinsonHyperlegible", "latin", STYLES,
               "Made for low vision: similar letters look different"),
    FontChoice("lexend", "Lexend", "Lexend", "latin", ("Regular", "Bold"),
               "Wide letters and spacing for smoother reading"),
    FontChoice("andika", "Andika", "Andika", "latin", STYLES,
               "Simple, clear letter shapes for new readers"),
    FontChoice("noto-sans", "Noto Sans", "NotoSans", "latin", STYLES,
               "A plain, familiar sans-serif"),
    FontChoice("noto-serif", "Noto Serif", "NotoSerif", "latin", STYLES,
               "A classic book typeface with serifs"),
)}

ARABIC_FONTS: Dict[str, FontChoice] = {f.id: f for f in (
    FontChoice("noto-sans-arabic", "Noto Sans Arabic", "NotoSansArabic", "arabic",
               note="Clear modern Arabic letters"),
    FontChoice("noto-naskh-arabic", "Noto Naskh Arabic", "NotoNaskhArabic", "arabic",
               note="Traditional book style (Naskh)"),
    FontChoice("amiri", "Amiri", "Amiri", "arabic",
               note="Classic Naskh used in printed books"),
    FontChoice("ibm-plex-sans-arabic", "IBM Plex Sans Arabic", "IBMPlexSansArabic", "arabic",
               note="Open, even letters"),
    FontChoice("tajawal", "Tajawal", "Tajawal", "arabic",
               note="Simple geometric letters"),
    FontChoice("readex-pro", "Readex Pro", "ReadexPro", "arabic",
               note="Wide, open letters (pairs with Lexend)"),
)}

DEFAULT_LATIN = "atkinson"
DEFAULT_ARABIC = "noto-sans-arabic"
FONT_FAMILY = LATIN_FONTS[DEFAULT_LATIN].family


def latin_choice(font_id: Optional[str]) -> FontChoice:
    return LATIN_FONTS.get(font_id or DEFAULT_LATIN, LATIN_FONTS[DEFAULT_LATIN])


def arabic_choice(font_id: Optional[str]) -> FontChoice:
    return ARABIC_FONTS.get(font_id or DEFAULT_ARABIC, ARABIC_FONTS[DEFAULT_ARABIC])


def font_catalog() -> Dict[str, List[Dict[str, str]]]:
    """The choices offered in the settings, for the user interface."""
    def entries(fonts: Dict[str, FontChoice]) -> List[Dict[str, str]]:
        return [{"id": f.id, "family": f.family, "note": f.note} for f in fonts.values()]
    return {"latin": entries(LATIN_FONTS), "arabic": entries(ARABIC_FONTS)}


def bundled_font_dir() -> Path:
    here = Path(__file__).resolve().parent / "fonts"
    if here.is_dir():
        return here
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "openlargeprint" / "exporters" / "fonts").is_dir():
        return Path(meipass) / "openlargeprint" / "exporters" / "fonts"
    return here


def font_path(choice: FontChoice, style: str = "Regular") -> Path:
    return bundled_font_dir() / choice.file(style)


FALLBACK_FILES = {"Regular": "DejaVuSans.ttf", "Bold": "DejaVuSans-Bold.ttf"}


@dataclass(frozen=True)
class FontSet:
    regular: str
    bold: str
    italic: str
    bold_italic: str
    fallback: str
    fallback_bold: str
    arabic: str
    arabic_bold: str = ""

    def __post_init__(self) -> None:
        if not self.arabic_bold:
            object.__setattr__(self, "arabic_bold", self.arabic)

    @property
    def bold_names(self) -> Tuple[str, ...]:
        return (self.bold, self.bold_italic, self.arabic_bold, self.fallback_bold)


_HELVETICA = FontSet("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
                     "Helvetica", "Helvetica-Bold", "Helvetica", "Helvetica-Bold")


def _register_family(prefix: str, files: Dict[str, Path]) -> Dict[str, str]:
    """Register the faces of one family and tie them together for <b> and <i>."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    names: Dict[str, str] = {}
    registered: Dict[Path, str] = {}
    for style in STYLES:
        path = files.get(style) or files.get("Bold" if "Bold" in style else "Regular") or files["Regular"]
        if path not in registered:
            name = f"{prefix}-{style}"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
            registered[path] = name
        names[style] = registered[path]
    for bold, italic, style in ((0, 0, "Regular"), (1, 0, "Bold"), (0, 1, "Italic"), (1, 1, "BoldItalic")):
        addMapping(names["Regular"], bold, italic, names[style])
    return names


@lru_cache(maxsize=16)
def output_fonts(latin: Optional[str] = None, arabic: Optional[str] = None) -> FontSet:
    """Register the chosen faces with ReportLab once per process."""
    directory = bundled_font_dir()
    latin_font, arabic_font = latin_choice(latin), arabic_choice(arabic)
    try:
        lat = _register_family(f"OLP-{latin_font.id}",
                               {s: directory / latin_font.file(s) for s in latin_font.styles})
        ara = _register_family(f"OLP-{arabic_font.id}",
                               {s: directory / arabic_font.file(s) for s in arabic_font.styles})
        fallback = _register_family("OLP-Fallback", {s: directory / f for s, f in FALLBACK_FILES.items()})
    except Exception as exc:
        log_safe_info(f"Bundled fonts unavailable ({type(exc).__name__}); using Helvetica")
        return _HELVETICA
    return FontSet(lat["Regular"], lat["Bold"], lat["Italic"], lat["BoldItalic"],
                   fallback["Regular"], fallback["Bold"], ara["Regular"], ara["Bold"])


@lru_cache(maxsize=64)
def _coverage(font_name: str) -> frozenset:
    from reportlab.pdfbase import pdfmetrics
    try:
        face = pdfmetrics.getFont(font_name).face
        return frozenset(face.charToGlyph.keys())
    except Exception:
        return frozenset()


def _is_arabic(ch: str) -> bool:
    code = ord(ch)
    return 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F or 0xFB50 <= code <= 0xFDFF \
        or 0xFE70 <= code <= 0xFEFF


def markup(text: str, fonts: Optional[FontSet] = None, base: Optional[str] = None) -> str:
    """Escape text for a ReportLab paragraph, switching font where the base font has no glyph.

    ``base`` is the paragraph's own font. Arabic letters go to the chosen Arabic
    font, Latin letters to the chosen Latin font, and anything neither covers to
    DejaVu Sans; spaces and common punctuation stay in whatever font is current.
    """
    fonts = fonts or output_fonts()
    base = base or fonts.regular
    covered = _coverage(base)
    if not covered:
        return escape(text)
    bold = base in fonts.bold_names
    arabic = fonts.arabic_bold if bold else fonts.arabic
    latin = fonts.bold if bold else fonts.regular
    fallback = fonts.fallback_bold if bold else fonts.fallback

    def pick(ch: str, current: Optional[str]) -> Optional[str]:
        """The font for one character; None means the paragraph's own font."""
        code = ord(ch)
        if not ch.isalnum() and code in _coverage(current or base):
            return current  # spaces and punctuation stay with the run they are in
        wanted = arabic if _is_arabic(ch) else latin if ch.isalpha() else None
        if wanted and code in _coverage(wanted):
            return None if wanted == base else wanted
        if code in covered:
            return None
        for name in ((arabic, fallback, latin) if _is_arabic(ch) else (latin, fallback, arabic)):
            if name != base and code in _coverage(name):
                return name
        return None

    out: List[str] = []
    run: List[str] = []
    run_font: Optional[str] = None
    for ch in text:
        font = pick(ch, run_font)
        if font != run_font and run:
            chunk = escape("".join(run))
            out.append(f'<font name="{run_font}">{chunk}</font>' if run_font else chunk)
            run = []
        run_font = font
        run.append(ch)
    if run:
        chunk = escape("".join(run))
        out.append(f'<font name="{run_font}">{chunk}</font>' if run_font else chunk)
    return "".join(out)


def ensure_arabic_font() -> str:
    return output_fonts().arabic


def css_font_stack(latin: Optional[str] = None, arabic: Optional[str] = None) -> str:
    return (f'"{latin_choice(latin).family}", "{arabic_choice(arabic).family}", '
            '"DejaVu Sans", "Segoe UI", Arial, sans-serif')
