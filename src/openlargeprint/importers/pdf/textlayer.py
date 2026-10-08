"""Native PDF text: characters to words (PDF-002, PDF-006).

Words are built from individual glyph boxes. A word ends at a real space
character, at a space PDFium inferred, or where the gap to the next glyph is
clearly wider than the line's own letter spacing. That keeps letter-spaced
headings and kerned body text intact without rewriting any character.

Text that the reader cannot see is reported separately: invisible render
modes, and text painted *underneath* a page-covering picture (the typical
"text under image" layer written by scanning software). Such text is a previous
tool's OCR, not the document's own text, so the page is recognised again
instead of trusting it.
"""

from __future__ import annotations

import ctypes
import statistics
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from .classifier import REPLACEMENT_GLYPHS
from .glyphs import map_symbol_char

INVISIBLE_RENDER_MODES = {3, 7}
FORCE_BOLD_FLAG = 0x40000
ITALIC_FLAG = 0x40


@dataclass
class Word:
    """A word in page space (points, origin top-left, y down)."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool = False
    italic: bool = False
    confidence: float = 1.0
    blank: bool = False  # a fill-in gap rather than source characters
    underline: bool = False
    visual_order: bool = False  # right-to-left script stored left to right (display order)

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def box(self) -> Tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class NativeText:
    words: List[Word] = field(default_factory=list)
    visible_chars: int = 0
    hidden_chars: int = 0
    broken_chars: int = 0


@dataclass
class _Char:
    ch: str
    x0: float
    y0: float
    x1: float
    y1: float
    base: float
    size: float
    bold: bool
    italic: bool
    space_before: bool
    font: str = ""


def page_box(page: pdfium.PdfPage) -> Tuple[float, float, float, float]:
    """The visible page area in PDF user space (handles inherited and trimmed boxes)."""
    rect = pdfium_c.FS_RECTF()
    if pdfium_c.FPDF_GetPageBoundingBox(page, ctypes.byref(rect)):
        return (min(rect.left, rect.right), min(rect.top, rect.bottom),
                max(rect.left, rect.right), max(rect.top, rect.bottom))
    left, bottom, right, top = page.get_cropbox()
    return left, bottom, right, top


class PageFrame:
    """Page space for one page: points, origin top-left, y down, text running left to right.

    PDFium's own page-to-device transform maps PDF user space into it, so the
    page's /Rotate and any extra quarter turn (``quarter``, clockwise) are applied
    the same way to glyphs, images, drawings and renders. Rendering with
    ``rotation=frame.degrees`` gives a bitmap in this same frame.
    """

    GRID = 8  # device units per point (PDFium returns whole device units)

    def __init__(self, page: pdfium.PdfPage, quarter: int = 0):
        self.page = page
        self.quarter = quarter % 4
        width, height = page.get_size()  # as displayed, /Rotate applied
        if self.quarter % 2:
            width, height = height, width
        self.width, self.height = float(width), float(height)

    @property
    def degrees(self) -> int:
        return self.quarter * 90

    @property
    def area(self) -> float:
        return max(1.0, self.width * self.height)

    def point(self, x: float, y: float) -> Tuple[float, float]:
        dx, dy = ctypes.c_int(0), ctypes.c_int(0)
        pdfium_c.FPDF_PageToDevice(self.page, 0, 0, int(round(self.width * self.GRID)),
                                   int(round(self.height * self.GRID)), self.quarter, x, y,
                                   ctypes.byref(dx), ctypes.byref(dy))
        return dx.value / self.GRID, dy.value / self.GRID

    def rect(self, left: float, bottom: float, right: float, top: float) -> Tuple[float, float, float, float]:
        (ax, ay), (bx, by) = self.point(left, bottom), self.point(right, top)
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)


def reading_quarter(page: pdfium.PdfPage, textpage: pdfium.PdfTextPage) -> int:
    """Clockwise quarter turns that make the page's Latin text run left to right.

    A page displayed with its text running down (a landscape table printed
    sideways in a portrait book, or a /Rotate page whose content was not turned)
    is read in the turned frame. Right-to-left letters are not counted, since
    they advance leftwards by nature; a page needs a clear majority to turn.
    """
    frame = PageFrame(page, 0)
    votes = [0, 0, 0, 0]
    previous = None
    for index in range(min(textpage.count_chars(), 4000)):
        code = pdfium_c.FPDFText_GetUnicode(textpage, index)
        ch = chr(code) if 0 < code <= 0x10FFFF else " "
        if not ch.isalnum() or is_rtl_char(ch):
            previous = None
            continue
        x, y = ctypes.c_double(0), ctypes.c_double(0)
        pdfium_c.FPDFText_GetCharOrigin(textpage, index, ctypes.byref(x), ctypes.byref(y))
        point = frame.point(x.value, y.value)
        if previous is not None:
            dx, dy = point[0] - previous[0], point[1] - previous[1]
            if 0.5 < abs(dx) + abs(dy) < 40:
                if abs(dx) >= abs(dy):
                    votes[0 if dx > 0 else 2] += 1
                else:
                    votes[3 if dy > 0 else 1] += 1
        previous = point
    best = max(range(4), key=lambda q: votes[q])
    total = sum(votes)
    if best and votes[best] >= 20 and votes[best] > 0.6 * total:
        return best
    return 0


def _hidden_text_objects(page: pdfium.PdfPage, page_area: float) -> set:
    """Text objects painted before a picture that covers (almost) the whole page."""
    order: List[Tuple[int, int, int]] = []  # (draw index, type, pointer)
    for index, obj in enumerate(page.get_objects(max_depth=8)):
        pointer = ctypes.cast(obj.raw, ctypes.c_void_p).value
        kind = obj.type
        if kind == pdfium_c.FPDF_PAGEOBJ_IMAGE:
            try:
                left, bottom, right, top = obj.get_bounds()
                if (right - left) * (top - bottom) >= 0.85 * page_area:
                    order.append((index, -1, pointer))
                    continue
            except Exception:
                continue
        if kind == pdfium_c.FPDF_PAGEOBJ_TEXT:
            order.append((index, kind, pointer))
    last_cover = max((i for i, kind, _ in order if kind == -1), default=-1)
    if last_cover < 0:
        return set()
    return {pointer for i, kind, pointer in order if kind == pdfium_c.FPDF_PAGEOBJ_TEXT and i < last_cover}


def _font_style(textpage, index: int, cache: Dict[int, Tuple[bool, bool, str]], obj_key) -> Tuple[bool, bool, str]:
    if obj_key in cache:
        return cache[obj_key]
    flags = ctypes.c_int(0)
    buffer = ctypes.create_string_buffer(256)
    length = pdfium_c.FPDFText_GetFontInfo(textpage, index, buffer, 256, ctypes.byref(flags))
    name = buffer.value.decode("utf-8", "ignore").lower() if length else ""
    weight = pdfium_c.FPDFText_GetFontWeight(textpage, index)
    bold = (weight >= 600) or bool(flags.value & FORCE_BOLD_FLAG) or any(
        tag in name for tag in ("bold", "black", "heavy", "semibold", "demi"))
    italic = bool(flags.value & ITALIC_FLAG) or "italic" in name or "oblique" in name
    cache[obj_key] = (bold, italic, name)
    return bold, italic, name


def extract_native_text(page: pdfium.PdfPage, textpage: pdfium.PdfTextPage,
                        frame: PageFrame) -> NativeText:
    """Visible words on the page, in the frame's page space."""
    result = NativeText()
    count = textpage.count_chars()
    if count <= 0:
        return result
    hidden_objects = _hidden_text_objects(page, frame.area)
    style_cache: Dict[int, Tuple[bool, bool, str]] = {}
    mode_cache: Dict[int, bool] = {}

    chars: List[_Char] = []
    pending_space = False
    for index in range(count):
        code = pdfium_c.FPDFText_GetUnicode(textpage, index)
        if not code or code > 0x10FFFF:
            continue
        ch = chr(code)
        if ch in "\r\n\t" or ch.isspace():
            pending_space = True
            continue
        if 0xFFFE <= code or ch in REPLACEMENT_GLYPHS or (0xE000 <= code <= 0xF8FF and not map_symbol_char(ch, "")):
            result.broken_chars += 1
        obj = pdfium_c.FPDFText_GetTextObject(textpage, index)
        key = ctypes.cast(obj, ctypes.c_void_p).value if obj else 0
        if key not in mode_cache:
            invisible = False
            if obj:
                invisible = pdfium_c.FPDFTextObj_GetTextRenderMode(obj) in INVISIBLE_RENDER_MODES
            mode_cache[key] = invisible or key in hidden_objects
        if mode_cache[key]:
            result.hidden_chars += 1
            continue
        left, bottom, right, top = textpage.get_charbox(index, loose=True)
        if right - left <= 0 and top - bottom <= 0:
            continue
        x0, y_top, x1, y_bottom = frame.rect(left, bottom, right, top)
        if x1 <= 0 or x0 >= frame.width or y_bottom <= 0 or y_top >= frame.height:
            continue  # outside the visible page
        size = float(pdfium_c.FPDFText_GetFontSize(textpage, index)) or (y_bottom - y_top)
        x = ctypes.c_double(0)
        y = ctypes.c_double(0)
        pdfium_c.FPDFText_GetCharOrigin(textpage, index, ctypes.byref(x), ctypes.byref(y))
        _, base = frame.point(x.value, y.value)
        bold, italic, font_name = _font_style(textpage, index, style_cache, key)
        mapped = map_symbol_char(ch, font_name)
        if mapped:
            ch = mapped
        # Typographic ligatures (fi, fl, ffi) are one glyph but two or three letters.
        ch = unicodedata.normalize("NFKC" if 0xFB00 <= ord(ch[0]) <= 0xFB06 else "NFC", ch)
        # The nominal size is often 1pt with the real size in the text matrix, so the
        # glyph's loose box (ascent to descent, about 1.2 em) is the dependable measure.
        if y_bottom > y_top:
            size = (y_bottom - y_top) / 1.2
        size = max(1.0, size)
        room = ((chars[-1].x0 - x1) if chars and (is_rtl_char(ch) or is_rtl_char(chars[-1].ch))
                else (x0 - chars[-1].x1) if chars else 0.0)
        if pending_space and chars and abs(base - chars[-1].base) < 0.3 * size \
                and room < 0.06 * size:
            pending_space = False  # a space character with no room for it (inside a ligature)
        chars.append(_Char(ch, x0, y_top, x1, y_bottom, base, size, bold, italic, pending_space, font_name))
        pending_space = False
        result.visible_chars += 1

    result.words = _chars_to_words(chars)
    return result


def is_rtl_char(ch: str) -> bool:
    code = ord(ch[0]) if ch else 0
    return 0x0590 <= code <= 0x08FF or 0xFB1D <= code <= 0xFDFF or 0xFE70 <= code <= 0xFEFF


def _chars_to_words(chars: List[_Char]) -> List[Word]:
    """Split the glyph stream into words using spaces and spacing statistics."""
    if not chars:
        return []
    # Runs of glyphs that share a baseline and advance in their writing
    # direction: rightwards for Latin, leftwards for Arabic and Hebrew.
    def advance_gap(prev: _Char, ch: _Char) -> float:
        if is_rtl_char(ch.ch) or is_rtl_char(prev.ch):
            if ch.x1 <= prev.x1 + 0.25 * prev.size:
                return prev.x0 - ch.x1
        return ch.x0 - prev.x1

    runs: List[List[_Char]] = []
    current: List[_Char] = []
    for ch in chars:
        if current:
            prev = current[-1]
            same_line = abs(ch.base - prev.base) <= 0.45 * max(ch.size, prev.size)
            forward = ch.x0 >= prev.x0 - 0.25 * prev.size
            backward = (is_rtl_char(ch.ch) or is_rtl_char(prev.ch)) and ch.x1 <= prev.x1 + 0.25 * prev.size
            if not (same_line and (forward or backward)):
                runs.append(current)
                current = []
        current.append(ch)
    if current:
        runs.append(current)

    words: List[Word] = []
    for run in runs:
        rtl_steps = [run[i].x0 > run[i - 1].x0 for i in range(1, len(run))
                     if is_rtl_char(run[i].ch) and is_rtl_char(run[i - 1].ch)]
        visual = bool(rtl_steps) and sum(rtl_steps) * 2 > len(rtl_steps)
        gaps = [advance_gap(run[i - 1], run[i]) for i in range(1, len(run)) if not run[i].space_before]
        sizes = [c.size for c in run]
        size = statistics.median(sizes)
        # Letter spacing (tracking) can be a third of an em or more in headings and in
        # text set after them; word breaks are mostly marked by space characters.
        tight = [g for g in gaps if g < 0.6 * size]
        tracking = statistics.median(tight) if tight else 0.0
        threshold = max(0.0, tracking) + 0.2 * size
        word: List[_Char] = []
        for i, ch in enumerate(run):
            if word:
                gap = advance_gap(word[-1], ch)
                font_change = ch.font != word[-1].font and gap > 0.08 * size
                if ch.space_before or gap > threshold or font_change:
                    words.append(_make_word(word, visual))
                    word = []
            word.append(ch)
        if word:
            words.append(_make_word(word, visual))
    return words


def _make_word(chars: List[_Char], visual: bool = False) -> Word:
    bold = sum(c.bold for c in chars) * 2 >= len(chars)
    italic = sum(c.italic for c in chars) * 2 >= len(chars)
    return Word(
        text="".join(c.ch for c in chars),
        x0=min(c.x0 for c in chars), y0=min(c.y0 for c in chars),
        x1=max(c.x1 for c in chars), y1=max(c.y1 for c in chars),
        size=statistics.median(c.size for c in chars), bold=bold, italic=italic,
        visual_order=visual and any(is_rtl_char(c.ch) for c in chars),
    )
