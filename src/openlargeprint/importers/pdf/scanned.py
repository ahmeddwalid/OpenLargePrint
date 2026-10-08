"""Recognition output to page-space words (PDF-003, OCR-004).

The recogniser returns lines with token boxes. Tokens are grouped back into
words using the spaces in the recognised line itself, so the text stays exactly
as recognised while each word still knows where it sits on the page.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from openlargeprint.ocr.base import EnginePageResult, OcrDetectedLine
from .glyphs import clean_recognized_text
from .textlayer import Word


def _poly_box(polygon: Sequence[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _line_words(line: OcrDetectedLine, text: str) -> List[Tuple[str, Tuple[float, float, float, float], float]]:
    """Split one recognised line into (word, pixel box, confidence)."""
    lx0, ly0, lx1, ly1 = _poly_box(line.polygon)
    parts = text.split()
    if not parts:
        return []
    tokens = [(clean_recognized_text(t.text).strip(), _poly_box(t.polygon), t.confidence)
              for t in line.words if t.text and t.text.strip()]
    if tokens:
        # Walk the line text, consuming tokens in order; spaces in the text end words.
        result = []
        pos = 0
        current_text, current_boxes, current_conf = "", [], []
        ok = True
        for token, box, conf in tokens:
            skipped = 0
            while pos < len(text) and text[pos].isspace():
                pos += 1
                skipped += 1
            found = text.find(token, pos)
            if found != pos:
                ok = False
                break
            if skipped and current_text:
                result.append((current_text, current_boxes, current_conf))
                current_text, current_boxes, current_conf = "", [], []
            current_text += token
            current_boxes.append(box)
            current_conf.append(conf)
            pos += len(token)
        if ok and pos == len(text.rstrip()):
            if current_text:
                result.append((current_text, current_boxes, current_conf))
            return [(t, (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)),
                     min(cs)) for t, bs, cs in result]
    # No usable token boxes: share the line width out by character count.
    total = sum(len(p) for p in parts) + len(parts) - 1
    width = max(1.0, lx1 - lx0)
    out = []
    cursor = 0
    for part in parts:
        a = lx0 + width * cursor / total
        b = lx0 + width * (cursor + len(part)) / total
        out.append((part, (a, ly0, b, ly1), line.confidence))
        cursor += len(part) + 1
    return out


def ocr_words(result: EnginePageResult, scale: float, offset: Tuple[float, float] = (0.0, 0.0)) -> List[Word]:
    """Recognised lines -> words in page points (``scale`` = pixels per point)."""
    words: List[Word] = []
    ox, oy = offset
    for line in result.lines:
        text = clean_recognized_text(line.text).strip()
        if not text:
            continue
        lx0, ly0, lx1, ly1 = _poly_box(line.polygon)
        size = max(4.0, (ly1 - ly0) / scale * 0.78)
        # The line score is the recogniser's own judgement of the whole line;
        # single-token scores swing on punctuation and are only used for geometry.
        for word_text, (x0, y0, x1, y1), _ in _line_words(line, text):
            words.append(Word(
                text=word_text, x0=ox + x0 / scale, y0=oy + ly0 / scale, x1=ox + x1 / scale,
                y1=oy + ly1 / scale, size=size, confidence=line.confidence,
            ))
    return words
