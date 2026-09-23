"""Cross-platform font resolution for PDF and HTML output (OUT-001, LANG-001).

The configured ``font_family`` must actually reach every output, not just DOCX.
This module locates a matching TrueType font on the host (Linux/macOS/Windows),
registers it with ReportLab, and produces a CSS family stack for HTML output.
When nothing matches, it degrades safely to the built-in Helvetica family.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from openlargeprint.security.isolation import log_safe_info

_HELVETICA_MAP = {
    "normal": "Helvetica",
    "bold": "Helvetica-Bold",
    "italic": "Helvetica-Oblique",
    "boldItalic": "Helvetica-BoldOblique",
}

# Family-name aliases that map to fonts PDF viewers always have available.
_BUILTIN_ALIASES = {
    "helvetica": "Helvetica",
    "arial": "Helvetica",
    "liberation sans": "Helvetica",
    "sans": "Helvetica",
    "sans-serif": "Helvetica",
}

_ARABIC_CANDIDATES: List[str] = [
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/google-noto-vf/NotoSansArabic[wght].ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/local/share/fonts/a/Amiri_Regular.ttf",
    "/usr/share/fonts/amiri-quran-fonts/AmiriQuran.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/GeezaPro.ttc",
    "/Library/Fonts/Arial.ttf",
    # Windows
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    r"C:\Windows\Fonts\times.ttf",
]

_registered: Dict[str, str] = {}
_arabic_font_name: Optional[str] = None


def _bundled_font_dirs() -> List[Path]:
    """Return directories containing bundled project fonts (e.g. ui/public/fonts)."""
    dirs: List[Path] = []
    # 1. Search relative to this file within the repository checkout
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        for sub in (
            Path("ui") / "public" / "fonts",
            Path("ui") / "dist" / "fonts",
            Path("fonts"),
        ):
            cand = parent / sub
            if cand.is_dir() and cand not in dirs:
                dirs.append(cand)

    # 2. PyInstaller onefile/onedir bundle paths
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_fonts = Path(meipass) / "fonts"
        if meipass_fonts.is_dir() and meipass_fonts not in dirs:
            dirs.append(meipass_fonts)

    # 3. Check adjacent to the running Python / sidecar executable
    exe_dir = Path(sys.executable).parent
    for sub in ("fonts", "ui/public/fonts", "ui/dist/fonts"):
        cand = exe_dir / sub
        if cand.is_dir() and cand not in dirs:
            dirs.append(cand)

    return dirs


def _candidate_font_dirs() -> List[Path]:
    """Return platform-appropriate font directories to search."""
    dirs: List[str] = [
        os.environ.get("OPENLARGEPRINT_FONTS_DIR", ""),
    ]
    for b in _bundled_font_dirs():
        dirs.append(str(b))

    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        local = os.environ.get("LOCALAPPDATA", "")
        dirs += [
            str(Path(windir) / "Fonts"),
            str(Path(local) / "Microsoft" / "Windows" / "Fonts") if local else "",
        ]
    elif sys.platform == "darwin":
        dirs += [
            "/System/Library/Fonts",
            "/System/Library/Fonts/Supplemental",
            "/Library/Fonts",
            str(Path.home() / "Library" / "Fonts"),
        ]
    else:
        dirs += [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            str(Path.home() / ".local" / "share" / "fonts"),
            str(Path.home() / ".fonts"),
        ]

    return [Path(d) for d in dirs if d and Path(d).is_dir()]



def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def find_font_file(family: str, bold: bool = False, italic: bool = False) -> Optional[Path]:
    """Locate a TTF matching ``family`` (with a bold/italic preference)."""
    target = _normalize(family)
    if not target:
        return None

    style_tokens = []
    if bold:
        style_tokens.append("bold")
    if italic:
        style_tokens.append("italic")

    best: Optional[Path] = None
    best_score = -1

    for directory in _candidate_font_dirs():
        try:
            candidates = list(directory.rglob("*.ttf"))
        except OSError:
            continue
        for path in candidates:
            stem = _normalize(path.stem)
            if target not in stem:
                continue
            score = len(target)
            if bold and "bold" in stem:
                score += 2
            if italic and ("italic" in stem or "oblique" in stem):
                score += 2
            if score > best_score:
                best_score = score
                best = path

    return best


def register_reportlab_font(path: Path, name: str) -> Optional[str]:
    """Register a TTF with ReportLab; return the font name or ``None`` on failure."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdfmetrics.registerFont(TTFont(name, str(path)))
        return name
    except Exception as exc:
        log_safe_info(f"Could not register font {path.name}: {type(exc).__name__}")
        return None


def resolve_reportlab_family(family: str, fallback: str = "Arial") -> Dict[str, str]:
    """Resolve a document family into ReportLab font names for each face.

    Falls back to Helvetica variants when no on-host match exists, so PDF export
    never fails because of typography.
    """
    key = f"{family}|{fallback}"
    if key in _registered:
        return {face: _registered[key] for face in _HELVETICA_MAP}  # pragma: no cover

    result = dict(_HELVETICA_MAP)

    normalized_family = family.strip().lower()
    if normalized_family in _BUILTIN_ALIASES:
        return result

    faces = {
        "normal": (False, False, "OpenLargePrint-Regular"),
        "bold": (True, False, "OpenLargePrint-Bold"),
        "italic": (False, True, "OpenLargePrint-Italic"),
        "boldItalic": (True, True, "OpenLargePrint-BoldItalic"),
    }
    resolved: Dict[str, str] = {}
    found_any = False
    for face, (bold, italic, reg_name) in faces.items():
        font_file = find_font_file(family, bold=bold, italic=italic)
        if font_file is None:
            resolved[face] = _HELVETICA_MAP[face]
            continue
        registered = register_reportlab_font(font_file, reg_name)
        if registered:
            resolved[face] = registered
            found_any = True
        else:
            resolved[face] = _HELVETICA_MAP[face]

    if found_any:
        log_safe_info(f"Resolved document font '{family}' from the host font directories")
        return resolved
    return result


def ensure_arabic_font() -> str:
    """Return a ReportLab font name that can render Arabic (LANG-001, LANG-002)."""
    global _arabic_font_name
    if _arabic_font_name is not None:
        return _arabic_font_name

    # 1. Prefer bundled NotoSansArabic font from the project distribution
    for directory in _bundled_font_dirs():
        bundled_arabic = directory / "NotoSansArabic.ttf"
        if bundled_arabic.is_file():
            registered = register_reportlab_font(bundled_arabic, "OpenLargePrintArabic")
            if registered:
                _arabic_font_name = registered
                return registered

    # 2. Host candidate paths
    for path in _ARABIC_CANDIDATES:
        if not os.path.exists(path):
            continue
        registered = register_reportlab_font(Path(path), "OpenLargePrintArabic")
        if registered:
            _arabic_font_name = registered
            return registered

    # 3. Last resort: search directory listings for an Arabic-capable family.
    for family in ("NotoSansArabic", "Amiri", "Scheherazade", "DejaVuSans"):
        font_file = find_font_file(family)
        if font_file is not None:
            registered = register_reportlab_font(font_file, "OpenLargePrintArabic")
            if registered:
                _arabic_font_name = registered
                return registered

    _arabic_font_name = "Helvetica"
    return _arabic_font_name


def css_font_stack(family: str, fallback: str = "Arial") -> str:
    """Build a CSS font-family stack that prefers ``family`` with safe fallbacks."""
    parts = [f'"{family}"']
    if fallback and fallback.lower() != family.lower():
        parts.append(f'"{fallback}"')
    parts.append('"Segoe UI"')
    parts.append("Roboto")
    parts.append("Arial")
    parts.append("sans-serif")
    return ", ".join(parts)
