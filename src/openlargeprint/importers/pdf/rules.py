"""Horizontal and vertical rules found on the rendered page.

Exercise books print fill-in gaps as dotted or solid lines. Those lines can be
vector paths, part of a background picture, or a scan, so they are found on the
rendered page rather than in the PDF's drawing commands. The same pass finds
ruling lines that separate table rows and columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np
from PIL import Image


@dataclass
class Rule:
    x0: float
    y0: float
    x1: float
    y1: float
    vertical: bool = False

    @property
    def length(self) -> float:
        return (self.y1 - self.y0) if self.vertical else (self.x1 - self.x0)

    @property
    def y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def x(self) -> float:
        return (self.x0 + self.x1) / 2


def find_rules(image: Image.Image, page_width: float, page_height: float,
               text_boxes: Sequence[Sequence[float]] = (), ink: int = 200) -> List[Rule]:
    """Thin straight lines (solid or dotted) in page-space points.

    Ink inside ``text_boxes`` is ignored first, so the bottoms of a line of
    letters can never be mistaken for a printed line.
    """
    import cv2

    gray = np.asarray(image.convert("L"))
    px_per_pt = image.width / max(1.0, page_width)
    dark = (gray < ink).astype(np.uint8)
    for x0, y0, x1, y1 in text_boxes:
        a, b = max(0, int(x0 * px_per_pt) - 1), min(dark.shape[1], int(x1 * px_per_pt) + 2)
        c, d = max(0, int(y0 * px_per_pt) - 1), min(dark.shape[0], int(y1 * px_per_pt) + 1)
        if a < b and c < d:
            dark[c:d, a:b] = 0
    rules: List[Rule] = []

    def collect(mask: np.ndarray, vertical: bool, min_len_px: int, max_thick_px: int) -> None:
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for i in range(1, count):
            x, y, w, h, _ = stats[i]
            length, thick = (h, w) if vertical else (w, h)
            if length < min_len_px or thick > max_thick_px:
                continue
            rules.append(Rule(x / px_per_pt, y / px_per_pt, (x + w) / px_per_pt,
                              (y + h) / px_per_pt, vertical=vertical))

    min_len = max(12, int(14 * px_per_pt))
    thick = max(3, int(2.2 * px_per_pt))
    # Horizontal: bridge the dots of a dotted line, then keep long thin runs.
    joined = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(2.5 * px_per_pt)), 1)))
    horizontal = cv2.morphologyEx(joined, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1)))
    collect(horizontal, False, min_len, thick)
    vertical = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(min_len, int(18 * px_per_pt)))))
    collect(vertical, True, max(min_len, int(18 * px_per_pt)), thick)
    return rules


def underlined_words(rule: Rule, words: Sequence) -> list:
    """Words a rule sits directly beneath (or through): an underline, not an answer gap."""
    found = []
    for word in words:
        if not any(ch.isalnum() for ch in word.text):
            continue  # punctuation touching an answer line does not make it an underline
        overlap = min(rule.x1, word.x1) - max(rule.x0, word.x0)
        if overlap <= 0.6 * max(1.0, word.x1 - word.x0):
            continue
        if word.y0 - 0.1 * word.size <= rule.y <= word.y1 + 0.45 * word.size:
            found.append(word)
    if not found:
        return []
    covered = sum(min(rule.x1, w.x1) - max(rule.x0, w.x0) for w in found)
    extent = max(w.x1 for w in found) - min(w.x0 for w in found)
    size = max(w.size for w in found)
    # A box edge runs on past the words above it; an underline stops with them.
    if rule.length > extent + 2.5 * size:
        return []
    return found if covered > 0.25 * rule.length else []


def is_underline(rule: Rule, words: Sequence) -> bool:
    return bool(underlined_words(rule, words))
