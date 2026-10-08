"""Turn layout regions and words into ordered DocumentIR blocks (PDF-003, PDF-006, DOC-002).

The same assembler serves native pages (words from the PDF's text) and scanned
pages (words from recognition), so both paths produce the same structure:
headings, paragraphs, numbered exercise items, dialogue lines, tables, figures
with their captions, footnotes and boxed notes.

Text is never invented or reworded. The only additions are fill-in blanks,
which stand for printed answer lines that sit between words, and they are
marked as such in the word stream.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from openlargeprint.ir.models import (
    Block,
    BlockType,
    ExtractionMethod,
    ImageAsset,
    InlineStyle,
    TableStructure,
)
from openlargeprint.layout.regions import (
    LayoutRegion,
    RegionKind,
    TEXT_KINDS,
    coverage,
    to_ir_bbox,
    union_box,
)
from openlargeprint.text.direction import detect_language, detect_text_direction
from .rules import Rule, underlined_words
from .textlayer import Word, is_rtl_char

BLANK_TEXT = "______"

MARKER_RE = re.compile(
    r"^(?:"
    r"[•●○◦▪▫■□☐☑☒❑❒❏❐"
    r"◆◇►▶➢➤→➔✓✔✗✘☆★\-–—*]"
    r"(?=\s|$)"
    r"|\(?\d{1,3}(?:\.\d{1,3})*[.)]?(?=\s)"
    r"|\d{1,3}(?=[A-Z][a-z]{0,11}:\s)"
    r"|\(?[a-hA-H][.)](?=\s)"
    r"|\([ivx]{1,4}\)(?=\s)"
    r"|[A-Z][a-z]{0,11}:(?=\s)"
    r")"
)
DIALOGUE_RE = re.compile(r"^[A-Z][a-z]{0,11}:\s")
FOOTNOTE_START_RE = re.compile(r"^(?:\d{1,3}[.)]?\s|[*†‡¹²³]|\[\d{1,3}\])")
SPEAKER_AFTER_NUMBER_RE =re.compile(r"^\d{1,3}[.)]?\s+([A-Z][a-z]{0,11}:)\s")


@dataclass
class TextLine:
    words: List[Word]

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def x1(self) -> float:
        return max(w.x1 for w in self.words)

    @property
    def y0(self) -> float:
        return min(w.y0 for w in self.words)

    @property
    def y1(self) -> float:
        return max(w.y1 for w in self.words)

    @property
    def size(self) -> float:
        real = [w.size for w in self.words if not w.blank]
        return statistics.median(real) if real else self.words[0].size

    @property
    def bold(self) -> bool:
        real = [w for w in self.words if not w.blank]
        return bool(real) and sum(len(w.text) for w in real if w.bold) * 2 > sum(len(w.text) for w in real)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def confidence(self) -> float:
        return min((w.confidence for w in self.words), default=1.0)

    @property
    def box(self) -> Tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class AssembledPage:
    blocks: List[Block] = field(default_factory=list)
    printed_page: Optional[str] = None
    heading_sizes: Dict[str, float] = field(default_factory=dict)
    body_sizes: List[float] = field(default_factory=list)


def _is_rtl_line(words: Sequence[Word]) -> bool:
    rtl = sum(1 for w in words for c in w.text if is_rtl_char(c))
    ltr = sum(1 for w in words for c in w.text if c.isalpha() and not is_rtl_char(c))
    return rtl > ltr


def _rtl_reading_order(words: List[Word]) -> List[Word]:
    """Words of a right-to-left line in reading order; Latin or number runs keep their own order."""
    runs: List[List[Word]] = []
    for word in words:  # left to right on the page
        rtl = any(is_rtl_char(c) for c in word.text)
        if runs and (any(is_rtl_char(c) for w in runs[-1] for c in w.text)) == rtl:
            runs[-1].append(word)
        else:
            runs.append([word])
    ordered: List[Word] = []
    for run in reversed(runs):
        ordered.extend(reversed(run) if any(is_rtl_char(c) for w in run for c in w.text) else run)
    return ordered


def group_lines(words: Sequence[Word], split_gap: float = 2.5) -> List[TextLine]:
    """Words -> visual lines, top to bottom, left to right."""
    lines: List[List[Word]] = []
    for word in sorted(words, key=lambda w: (w.cy, w.x0)):
        placed = False
        for line in reversed(lines[-6:]):
            ref = line[-1]
            mid = statistics.median(w.cy for w in line)
            tol = 0.42 * max(ref.size, word.size, 1.0)
            overlap = min(word.y1, max(w.y1 for w in line)) - max(word.y0, min(w.y0 for w in line))
            if abs(word.cy - mid) <= tol or overlap >= 0.6 * min(word.height, ref.height):
                line.append(word)
                placed = True
                break
        if not placed:
            lines.append([word])
    result: List[TextLine] = []
    for line in lines:
        line.sort(key=lambda w: w.x0)
        if _is_rtl_line(line) and not any(w.visual_order for w in line):
            line = _rtl_reading_order(line)
        run: List[Word] = [line[0]]
        for word in line[1:]:
            spacing = max(word.x0 - run[-1].x1, run[-1].x0 - word.x1)
            if spacing > split_gap * max(word.size, run[-1].size):
                result.append(TextLine(run))
                run = [word]
            else:
                run.append(word)
        result.append(TextLine(run))
    result.sort(key=lambda l: (round(l.y0, 0), l.x0))
    return result


def insert_blanks(words: List[Word], rules: Sequence[Rule], regions: Sequence[LayoutRegion],
                  page_width: float) -> List[Word]:
    """Add a blank word for each answer line that sits in running text."""
    real = [w for w in words if not w.blank]
    if not real:
        return words
    body = statistics.median(w.size for w in real)
    blanks: List[Word] = []
    for rule in rules:
        if rule.vertical or rule.length < 1.2 * body or rule.length > 0.62 * page_width:
            continue
        holder = None
        for region in regions:
            if coverage((rule.x0, rule.y0, rule.x1, rule.y1 + 0.1), region.box) > 0.5:
                holder = region
                break
        if holder is not None and holder.kind not in (RegionKind.TEXT, RegionKind.LIST, RegionKind.ASIDE,
                                                      RegionKind.CONTENTS):
            continue
        near = [w for w in real if min(rule.x1, w.x1) - max(rule.x0, w.x0) > -3 * body
                and abs(w.y1 - rule.y) < 1.4 * body]
        decorated = underlined_words(rule, near)
        if decorated:
            for word in decorated:
                word.underline = True
            continue
        same_row = [w for w in real if abs(w.y1 - rule.y) <= 0.75 * w.size]
        # An answer line sits between or right after words; a line with no text
        # beside it is a border or separator.
        beside = [w for w in same_row
                  if (w.x1 <= rule.x0 + 2 and rule.x0 - w.x1 < 2.5 * w.size)
                  or (w.x0 >= rule.x1 - 2 and w.x0 - rule.x1 < 2.5 * w.size)]
        if not beside:
            continue
        follower = [w for w in beside if w.x0 >= rule.x1 - 2]
        if holder is not None and holder.kind == RegionKind.CONTENTS and follower \
                and follower[0].text.strip(".").isdigit():
            continue  # dot leader in a table of contents, pointing at a page number
        intrusion = sum(max(0.0, min(rule.x1, w.x1) - max(rule.x0, w.x0)) for w in same_row)
        if intrusion > 0.3 * rule.length:
            continue  # words sit on it: an underline or a highlight edge, not a gap
        size = statistics.median(w.size for w in same_row) if same_row else body
        baseline = statistics.median(w.y1 for w in same_row) if same_row else rule.y
        blanks.append(Word(BLANK_TEXT, rule.x0, baseline - 0.8 * size, rule.x1, baseline,
                           size=size, blank=True))
    return words + blanks


def split_columns(words: Sequence[Word], min_share: float = 0.2) -> List[List[Word]]:
    """Side-by-side columns inside one region (text with glosses beside it, for example)."""
    real = [w for w in words if not w.blank]
    if len(real) < 6:
        return [list(words)]
    size = statistics.median(w.size for w in real)
    left = min(w.x0 for w in words)
    right = max(w.x1 for w in words)
    bins = int(right - left) + 2
    covered = [False] * bins
    for w in words:
        for i in range(max(0, int(w.x0 - left)), min(bins, int(w.x1 - left) + 1)):
            covered[i] = True
    cuts: List[float] = []
    start = None
    for i, c in enumerate(covered):
        if not c and start is None:
            start = i
        elif c and start is not None:
            if i - start >= 1.5 * size:
                cuts.append(left + (start + i) / 2)
            start = None
    if not cuts:
        return [list(words)]
    total = sum(len(w.text) for w in real)
    groups: List[List[Word]] = [[] for _ in range(len(cuts) + 1)]
    for w in words:
        groups[sum(1 for c in cuts if w.cx > c)].append(w)
    def substantial(group: List[Word]) -> bool:
        if not group:
            return False
        share = sum(len(w.text) for w in group if not w.blank) / max(1, total)
        span = max(w.x1 for w in group) - min(w.x0 for w in group)
        return share >= min_share and span >= 0.2 * (right - left)

    # A column too slight to stand alone (item numbers, speaker labels) joins its neighbour.
    merged: List[List[Word]] = []
    for group in groups:
        if merged and (not substantial(group) or not substantial(merged[-1])):
            merged[-1].extend(group)
        else:
            merged.append(list(group))
    return [g for g in merged if g]


def line_columns(lines: List[TextLine]) -> List[List[TextLine]]:
    """Two columns of short lines set close together (numbered items 1-3 beside 4-6).

    When every line sits wholly left or wholly right of one dividing position,
    and each side has several lines, the left column is read before the right.
    """
    if len(lines) < 4:
        return [lines]
    left_edge = min(l.x0 for l in lines)
    right_edge = max(l.x1 for l in lines)
    candidates = sorted({round(l.x0) for l in lines if l.x0 > left_edge + 0.25 * (right_edge - left_edge)})
    for split in candidates:
        left = [l for l in lines if l.x1 <= split + 1]
        right = [l for l in lines if l.x0 >= split - 1]
        if len(left) + len(right) == len(lines) and len(left) >= 2 and len(right) >= 2:
            starts = {round(l.x0 / 4) for l in right}
            if len(starts) <= 2:
                return [left, right]
    return [lines]


def _confidence(lines: Sequence[TextLine]) -> float:
    """Block confidence: the average line, pulled down by any line that was a real struggle."""
    if not lines:
        return 1.0
    scores = [l.confidence for l in lines]
    return min(statistics.mean(scores), min(scores) + 0.2)


def compose(lines: Sequence[TextLine]) -> Tuple[str, List[InlineStyle]]:
    """Join lines into reflowable text and record bold/italic/underline runs.

    A word broken by a hyphen at the end of a line is rejoined without a space,
    keeping the hyphen. Emphasis is only recorded when it marks part of the
    text: a block printed entirely in bold gets its weight from its type.
    """
    out = ""
    marks: List[Tuple[int, int, bool, bool, bool]] = []
    for line in lines:
        previous: Optional[Word] = None
        for i, word in enumerate(line.words):
            text = word.text
            if not text.strip():
                continue
            if out:
                if i == 0 and out.endswith("-") and not out.endswith(" -") and text[:1].islower():
                    pass
                elif (previous is not None and not word.blank and not previous.blank
                      and word.x0 - previous.x1 > 2.2 * max(word.size, previous.size)):
                    out += "\n"  # separate entries set apart on one line (a box of expressions)
                else:
                    out += " "
            previous = word
            start = len(out)
            out += text
            if not word.blank:
                marks.append((start, len(out), word.bold, word.italic, word.underline))
    styles: List[InlineStyle] = []
    for attr in (2, 3, 4):
        flagged = [m for m in marks if m[attr]]
        if not flagged or len(flagged) == len(marks):
            continue
        run_start, run_end = flagged[0][0], flagged[0][1]
        for m in flagged[1:]:
            gap = out[run_end:m[0]]
            if not gap.strip():
                run_end = m[1]
            else:
                styles.append(InlineStyle(start=run_start, end=run_end, bold=attr == 2,
                                          italic=attr == 3, underline=attr == 4))
                run_start, run_end = m[0], m[1]
        styles.append(InlineStyle(start=run_start, end=run_end, bold=attr == 2,
                                  italic=attr == 3, underline=attr == 4))
    return out, styles


def _join_lines(lines: Sequence[TextLine]) -> str:
    return compose(lines)[0]


def split_items(lines: Sequence[TextLine], one_per_line: bool = False) -> List[List[TextLine]]:
    """Paragraphs and list items inside one region."""
    if not lines:
        return []
    if one_per_line:
        return [[line] for line in lines]
    gaps = [lines[i].y0 - lines[i - 1].y1 for i in range(1, len(lines))]
    normal_gap = statistics.median(gaps) if gaps else 0.0
    items: List[List[TextLine]] = [[lines[0]]]
    for prev, line in zip(lines, lines[1:]):
        current = items[-1]
        size = max(line.size, prev.size)
        gap = line.y0 - prev.y1
        starts_item = bool(MARKER_RE.match(line.text))
        new = starts_item
        if gap > max(normal_gap + 0.45 * size, 0.55 * size):
            new = True
        first = current[0]
        if not new and MARKER_RE.match(first.text):
            # In a hanging-indent list, a line back at the marker's edge starts a new item.
            if len(current) > 1 and line.x0 < current[1].x0 - 0.6 * size and abs(line.x0 - first.x0) < 0.6 * size:
                new = True
        if (not new and not MARKER_RE.match(first.text) and line.x0 > prev.x0 + 1.2 * size
                and prev.text.rstrip().endswith((".", "!", "?", ":"))):
            new = True  # first-line indent of a new paragraph
        if (not new and len(current) <= 2 and all(l.bold for l in current) and not line.bold
                and prev.size >= line.size and not prev.text.rstrip().endswith((",", ";"))):
            new = True  # a bold heading line followed by plain body text
        if not any(ch.isalnum() for ch in line.text):
            new = False  # a stray full stop or answer line finishes the item above
        if new:
            items.append([line])
        else:
            current.append(line)
    return items


def _indent_level(item_x0: float, base_x0: float, size: float) -> int:
    step = max(1.0, 1.4 * size)
    return max(0, min(4, math.ceil((item_x0 - base_x0) / step - 0.35)))


def _split(indices: List[int], boxes, axis: int, slack: float) -> List[List[int]]:
    """Groups of boxes separated by empty space along one axis (0 = x, 1 = y)."""
    spans = sorted(((boxes[i][axis], boxes[i][axis + 2], i) for i in indices))
    groups: List[List[int]] = [[spans[0][2]]]
    reach = spans[0][1]
    for lo, hi, i in spans[1:]:
        if lo > reach + slack:
            groups.append([i])
        else:
            groups[-1].append(i)
        reach = max(reach, hi)
    return groups


def xy_cut_order(boxes: List[Tuple[float, float, float, float]], rtl: bool = False) -> List[int]:
    """Reading order without model guidance, for either writing direction.

    The page is cut into horizontal bands. A band joins the stretch above it
    while the two together still have a clear gutter running top to bottom, so
    a two-column page is read column by column (even when one column runs
    longer than the other), while a full-width title or footnote still starts
    a stretch of its own.
    """
    def columns(indices: List[int]) -> List[List[int]]:
        groups = _split(indices, boxes, 0, 6.0)
        return list(reversed(groups)) if rtl else groups

    def spans(group: List[int]) -> Tuple[float, float]:
        return min(boxes[i][0] for i in group), max(boxes[i][2] for i in group)

    def order(indices: List[int]) -> List[int]:
        if len(indices) <= 1:
            return indices
        bands = _split(indices, boxes, 1, 2.0)
        merged: List[List[int]] = []
        for band in bands:
            if merged and len(columns(merged[-1])) > 1 and len(columns(merged[-1] + band)) > 1:
                merged[-1].extend(band)
            else:
                merged.append(list(band))
        result: List[int] = []
        for band in merged:
            cols = columns(band)
            if len(cols) > 1:
                for col in cols:
                    result.extend(order(col) if len(col) < len(indices) else
                                  sorted(col, key=lambda i: (boxes[i][1], boxes[i][0])))
            else:
                result.extend(sorted(band, key=lambda i: (boxes[i][1], -boxes[i][0] if rtl else boxes[i][0])))
        return result
    return order(list(range(len(boxes))))


def _orphan_regions(lines: List[TextLine]) -> List[LayoutRegion]:
    """Group stray lines into text blocks by proximity."""
    regions: List[LayoutRegion] = []
    for line in sorted(lines, key=lambda l: (l.y0, l.x0)):
        target = None
        for region in regions:
            near_v = line.y0 - region.y1 <= 0.9 * line.size and line.y1 >= region.y0
            overlap = min(line.x1, region.x1) - max(line.x0, region.x0)
            if near_v and overlap > -0.5 * line.size:
                target = region
                break
        if target is None:
            regions.append(LayoutRegion(RegionKind.TEXT, *line.box, score=0.0, label="orphan"))
        else:
            target.x0, target.y0 = min(target.x0, line.x0), min(target.y0, line.y0)
            target.x1, target.y1 = max(target.x1, line.x1), max(target.y1, line.y1)
    return regions


def place_orphans(ordered: List[LayoutRegion], orphans: List[LayoutRegion]) -> List[LayoutRegion]:
    result = list(ordered)
    for orphan in sorted(orphans, key=lambda r: (r.y0, r.x0)):
        position = None
        for index, region in enumerate(result):
            x_overlap = min(orphan.x1, region.x1) - max(orphan.x0, region.x0)
            if x_overlap > 0 and region.y0 <= orphan.y0:
                position = index + 1
        if position is None:
            position = next((i for i, r in enumerate(result) if r.y0 > orphan.y0), len(result))
        result.insert(position, orphan)
    return result


def merge_line_fragments(regions: List[LayoutRegion], body_size: float,
                         blanks: Sequence[Word] = ()) -> List[LayoutRegion]:
    """Join a one-line text region to the text region it continues on the same line.

    The layout model sometimes ends a region at a wide gap (an answer line in an
    exercise), leaving the rest of that printed line as a separate region. Two
    real columns are both several lines tall, so they are never joined.
    """
    text_kinds = {RegionKind.TEXT, RegionKind.LIST}
    result = list(regions)
    changed = True
    while changed:
        changed = False
        for a in result:
            if a.kind not in text_kinds:
                continue
            for b in result:
                if b is a or b.kind not in text_kinds:
                    continue
                small = min(a.height, b.height)
                if small > 2.4 * body_size:
                    continue
                v_overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
                h_gap = max(a.x0, b.x0) - min(a.x1, b.x1)
                gap_left, gap_right = min(a.x1, b.x1), max(a.x0, b.x0)
                bridged = h_gap < 1.5 * body_size or any(
                    w.x0 <= gap_left + body_size and w.x1 >= gap_right - body_size
                    and max(a.y0, b.y0) - body_size <= w.cy <= min(a.y1, b.y1) + body_size for w in blanks)
                if v_overlap >= 0.5 * small and h_gap < 12 * body_size and bridged:
                    a.x0, a.y0 = min(a.x0, b.x0), min(a.y0, b.y0)
                    a.x1, a.y1 = max(a.x1, b.x1), max(a.y1, b.y1)
                    a.order = min(a.order, b.order)
                    result.remove(b)
                    changed = True
                    break
            if changed:
                break
    return result


def _append_text(target: Block, extra: Block) -> None:
    """Append ``extra``'s text to ``target``, keeping both blocks' emphasis offsets right."""
    shift = len(target.text or "") + 1
    target.text = f"{target.text} {extra.text}"
    target.styles = list(target.styles) + [
        s.model_copy(update={"start": s.start + shift, "end": s.end + shift}) for s in extra.styles]
    a, b = target.source_bounding_box, extra.source_bounding_box
    if a is not None and b is not None and target.source_page == extra.source_page:
        target.source_bounding_box = a.model_copy(update={
            "x0": min(a.x0, b.x0), "y0": min(a.y0, b.y0), "x1": max(a.x1, b.x1), "y1": max(a.y1, b.y1)})
    target.warnings.extend(w for w in extra.warnings if w not in target.warnings)


_OPEN_ENDING = re.compile(r"[\w,;\-\[\(–]$")


def _keep_sentences_whole(blocks: List[Block]) -> List[Block]:
    """Move a picture that the reading order dropped into the middle of a sentence.

    When text before a picture stops mid-sentence and the text after it carries
    on in lower case, the two halves are one paragraph: they are joined and the
    picture (with its caption) follows them.
    """
    text_types = (BlockType.PARAGRAPH, BlockType.LIST)
    result = list(blocks)
    i = 0
    while i < len(result) - 2:
        before = result[i]
        if before.type in text_types and before.text and _OPEN_ENDING.search(before.text.rstrip()):
            j = i + 1
            while j < len(result) and result[j].type in (BlockType.IMAGE, BlockType.CAPTION):
                j += 1
            if j > i + 1 and j < len(result):
                after = result[j]
                if (after.type == BlockType.PARAGRAPH and after.text and after.text[:1].islower()
                        and after.source_page == before.source_page):
                    _append_text(before, after)
                    before.confidence = min(before.confidence, after.confidence)
                    result.pop(j)
        i += 1
    return result


_CAPTION_RE = re.compile(r"^(figure|fig\.|table|chart|diagram|map|plate|photo)\s*[\dIVXivx]+[\w.\-]*\s*[:.\-–]?\s", re.I)


def _label_captions(blocks: List[Block]) -> List[Block]:
    """A short "Figure 4.1 ..." line right under a picture or over a table is its caption."""
    for i, block in enumerate(blocks):
        if block.type != BlockType.PARAGRAPH or not block.text or len(block.text) > 200:
            continue
        if not _CAPTION_RE.match(block.text):
            continue
        before = blocks[i - 1].type if i > 0 else None
        after = blocks[i + 1].type if i + 1 < len(blocks) else None
        if before == BlockType.IMAGE or after in (BlockType.TABLE, BlockType.IMAGE):
            block.type = BlockType.CAPTION
    return blocks


# Regions that come from the file's own drawing objects, not from the layout model.
GEOMETRIC_LABELS = {"orphan", "embedded_image", "vector_artwork", "ruled_table"}

FigureMaker = Callable[[LayoutRegion], Optional[ImageAsset]]
TableMaker = Callable[[LayoutRegion, List[Word]], Optional[Tuple[TableStructure, float, Optional[ImageAsset]]]]


class PageAssembler:
    def __init__(self, page_num: int, page_width: float, page_height: float,
                 method: ExtractionMethod, rtl: bool = False):
        self.page_num = page_num
        self.page_width = page_width
        self.page_height = page_height
        self.method = method
        self.rtl = rtl
        self._counter = 0

    def _id(self, kind: str) -> str:
        self._counter += 1
        return f"p{self.page_num}_{kind}{self._counter}"

    def _block(self, btype: BlockType, text: Optional[str], box, confidence: float = 1.0,
               **extra) -> Block:
        language = detect_language(text) if text else "en"
        direction = detect_text_direction(text) if text else detect_text_direction("")
        method = self.method
        if method == ExtractionMethod.NATIVE and text and confidence < 1.0:
            method = ExtractionMethod.OCR_FAST  # recognised words on a mixed page (native text is exact)
        return Block(
            id=self._id("b"), type=btype, text=text, language=language, text_direction=direction,
            source_page=self.page_num, source_bounding_box=to_ir_bbox(box, self.page_height),
            extraction_method=method, confidence=round(max(0.0, min(1.0, confidence)), 3), **extra,
        )

    def assemble(self, regions: List[LayoutRegion], words: List[Word],
                 make_figure: FigureMaker, make_table: TableMaker) -> AssembledPage:
        page = AssembledPage()
        page.body_sizes = [w.size for w in words if not w.blank]
        content_regions = [r for r in regions if not (r.kind == RegionKind.FIGURE and r.decorative)]
        if page.body_sizes:
            content_regions = merge_line_fragments(content_regions, statistics.median(page.body_sizes),
                                                   [w for w in words if w.blank])

        # Each word belongs to the region that holds most of it; small regions win ties.
        by_region: Dict[int, List[Word]] = {id(r): [] for r in content_regions}
        orphans: List[Word] = []
        for word in words:
            best, best_share = None, 0.5
            for region in content_regions:
                share = coverage(word.box, region.box)
                if share > best_share or (share == best_share and best is not None and region.area < best.area):
                    best, best_share = region, share
            if best is None:
                orphans.append(word)
            else:
                by_region[id(best)].append(word)

        # Section letters and unit numbers printed in the margin belong to the
        # heading on the same line ("A" + "Adjectives describing ...").
        targets = [r for r in content_regions if r.kind in (RegionKind.HEADING, RegionKind.TITLE)]
        for label in list(content_regions):
            held = by_region.get(id(label), [])
            if label.kind not in TEXT_KINDS or label in targets or not held:
                continue
            if sum(len(w.text) for w in held) > 3:
                continue
            mid = (label.y0 + label.y1) / 2
            beside = [h for h in targets if h.y0 - 4 <= mid <= h.y1 + 4 and 0 <= h.x0 - label.x1 < 90]
            if beside:
                by_region[id(beside[0])].extend(held)
                content_regions.remove(label)
                continue
            # A section letter beside plain text opens that section.
            text_beside = [t for t in content_regions if t.kind in (RegionKind.TEXT, RegionKind.LIST)
                           and t is not label and t.y0 - 4 <= mid <= t.y0 + 3 * max(w.size for w in held)
                           and 0 <= t.x0 - label.x1 < 90]
            if text_beside and all(w.text.isalpha() and w.text.isupper() for w in held):
                label.kind = RegionKind.HEADING
                label.order = text_beside[0].order - 0.5
        for word in list(orphans):
            if len(word.text) > 3:
                continue
            beside = [h for h in targets if h.y0 - 4 <= word.cy <= h.y1 + 4 and 0 <= h.x0 - word.x1 < 90]
            if beside:
                by_region[id(beside[0])].append(word)
                orphans.remove(word)

        # Punctuation left alone on a line (the full stop after a wrapped answer
        # line) belongs to the text right above it.
        for region in list(content_regions):
            held = by_region.get(id(region), [])
            if region.kind not in (RegionKind.TEXT, RegionKind.LIST) or not held:
                continue
            if any(ch.isalnum() for w in held for ch in w.text):
                continue
            size = max(w.size for w in held)
            above = [r for r in content_regions if r is not region and r.kind in (RegionKind.TEXT, RegionKind.LIST)
                     and -size <= region.y0 - r.y1 <= 2 * size and min(r.x1, region.x1) > max(r.x0, region.x0) - 2 * size]
            if above:
                target = min(above, key=lambda r: region.y0 - r.y1)
                by_region[id(target)].extend(held)
                target.y1 = max(target.y1, region.y1)
                content_regions.remove(region)

        # A blank only means something next to the words it belongs to.
        for key, held in by_region.items():
            if held and all(w.blank for w in held):
                held.clear()

        ordered = sorted(content_regions, key=lambda r: r.order)
        if ordered and (self.rtl or _is_rtl_line([w for w in words if not w.blank])):
            # The layout model reads columns left to right; Arabic pages start on the right.
            index = xy_cut_order([r.box for r in ordered], rtl=True)
            ordered = [ordered[i] for i in index]
        if orphans:
            orphan_regions = _orphan_regions(group_lines(orphans))
            for region in orphan_regions:
                by_region[id(region)] = [w for w in orphans if coverage(w.box, region.box) > 0.5]
            claimed = {id(w) for r in orphan_regions for w in by_region[id(r)]}
            leftover = [w for w in orphans if id(w) not in claimed]
            if leftover:
                region = LayoutRegion(RegionKind.TEXT, *union_box([w.box for w in leftover]), label="orphan")
                orphan_regions.append(region)
                by_region[id(region)] = leftover
            orphan_regions = [r for r in orphan_regions if not all(w.blank for w in by_region[id(r)])]
            if not any(r.label not in GEOMETRIC_LABELS for r in ordered):
                # No model reading order on this page (only pictures and grids found
                # from the file itself): order everything by the page geometry.
                combined = ordered + orphan_regions
                index = xy_cut_order([r.box for r in combined], rtl=self.rtl)
                ordered = [combined[i] for i in index]
            else:
                ordered = place_orphans(ordered, orphan_regions)

        notes: List[Block] = []
        for region in ordered:
            region_words = by_region.get(id(region), [])
            kind = region.kind
            if kind == RegionKind.PAGE_NUMBER:
                text = " ".join(w.text for w in sorted(region_words, key=lambda w: w.x0)).strip()
                if text:
                    page.printed_page = text
                    page.blocks.append(self._block(BlockType.ASIDE, text, region.box, role="page_number"))
                continue
            if kind in (RegionKind.HEADER, RegionKind.FOOTER):
                lines = group_lines(region_words)
                text = " ".join(l.text for l in lines).strip()
                if kind == RegionKind.FOOTER and FOOTNOTE_START_RE.match(text) and len(text) > 25:
                    # Numbered notes the model saw as a page footer: they are footnotes.
                    notes.extend(self._items(lines, BlockType.FOOTNOTE, False, page))
                elif text:
                    page.blocks.append(self._block(BlockType.ASIDE, text, region.box, role="running_text",
                                                   confidence=_confidence(lines)))
                continue
            if kind in (RegionKind.FIGURE, RegionKind.FORMULA):
                page.blocks.extend(self._figure(region, region_words, make_figure))
                continue
            if kind == RegionKind.TABLE:
                if any(not w.blank for w in region_words):
                    page.blocks.extend(self._table(region, region_words, make_table))
                else:
                    # A table with no readable words (pasted in as a picture) is kept as one.
                    page.blocks.extend(self._figure(region, [], make_figure))
                continue
            if not region_words:
                continue
            page.blocks.extend(self._text_region(region, region_words, page))
        # Footnotes close the page, wherever the reading order met them.
        blocks = _label_captions(self._join_item_continuations(page.blocks))
        page.blocks = [b for b in blocks if b.type != BlockType.FOOTNOTE] \
            + [b for b in blocks if b.type == BlockType.FOOTNOTE] + notes
        page.blocks = _keep_sentences_whole(page.blocks)
        return page

    @staticmethod
    def _join_item_continuations(blocks: List[Block]) -> List[Block]:
        """A plain line indented under a numbered item continues that item."""
        result: List[Block] = []
        for block in blocks:
            prev = result[-1] if result else None
            if (prev is not None and prev.type == BlockType.LIST and block.type == BlockType.PARAGRAPH
                    and block.role is None and prev.role != "dialogue" and prev.source_bounding_box
                    and block.source_bounding_box and block.text):
                a, b = prev.source_bounding_box, block.source_bounding_box
                indent = b.x0 - a.x0
                gap = a.y0 - b.y1
                if 3 <= indent <= 45 and -4 <= gap <= 20:
                    _append_text(prev, block)
                    prev.confidence = min(prev.confidence, block.confidence)
                    continue
            result.append(block)
        return result

    # -- region handlers -------------------------------------------------
    def _figure(self, region: LayoutRegion, words: List[Word], make_figure: FigureMaker) -> List[Block]:
        blocks: List[Block] = []
        lines = [line for column in split_columns(words, min_share=0.1) for line in group_lines(column)]
        figure_text = " ".join(l.text for l in lines).strip()
        asset = make_figure(region)
        if asset is not None:
            if figure_text:
                asset.alt_text = figure_text
            blocks.append(self._block(BlockType.IMAGE, None, region.box, image_asset=asset))
        # A panel number or single letter is legible in the enlarged picture itself.
        if figure_text and any(sum(c.isalpha() for c in token) >= 2 for token in figure_text.split()):
            blocks.append(self._block(
                BlockType.CAPTION, figure_text, union_box([w.box for w in words]),
                confidence=_confidence(lines),
                role="figure_text" if region.kind == RegionKind.FIGURE else "formula_text"))
        return blocks

    def _table(self, region: LayoutRegion, words: List[Word], make_table: TableMaker) -> List[Block]:
        if not words:
            return []
        built = make_table(region, words)
        if built is None:
            # No dependable grid: keep the rows as separate lines, flagged (TBL-002).
            blocks = []
            for line in group_lines(words, split_gap=1e9):
                block = self._block(BlockType.PARAGRAPH, line.text, line.box, confidence=line.confidence,
                                    role="table_row")
                blocks.append(block)
            if blocks:
                blocks[0].warnings.append("This table's columns could not be identified, so its rows are shown as lines of text. Compare with the original page.")
            return blocks
        structure, confidence, source_image = built
        block = self._block(BlockType.TABLE, structure.to_markdown_table(), region.box,
                            confidence=confidence, table_structure=structure, image_asset=source_image)
        if confidence < 0.6:
            block.warnings.append("This table's structure may not match the original. The original table is shown with it.")
        return [block]

    def _text_region(self, region: LayoutRegion, words: List[Word], page: AssembledPage) -> List[Block]:
        kind = region.kind
        lines = group_lines(words, split_gap=1e9 if kind in (RegionKind.TITLE, RegionKind.HEADING) else 2.5)
        if (self.method != ExtractionMethod.NATIVE and kind in (RegionKind.ASIDE, RegionKind.TEXT)
                and (region.x0 < 0.05 * self.page_width or region.x1 > 0.95 * self.page_width)):
            # Scans often catch a sliver of the facing page at the edge: broken
            # fragments of words. They are kept with the page details, not in the text.
            real = [w for w in words if not w.blank]
            if real and (statistics.mean(len(w.text) for w in real) < 3.5
                         or statistics.mean(w.confidence for w in real) < 0.8) and region.width < 0.2 * self.page_width:
                return [self._block(BlockType.ASIDE, _join_lines(lines), region.box,
                                    confidence=_confidence(lines), role="edge_text")]
        if kind in (RegionKind.TITLE, RegionKind.HEADING):
            text = _join_lines(lines)
            if not text:
                return []
            block = self._block(BlockType.HEADING, text, region.box, level=1 if kind == RegionKind.TITLE else 2,
                                confidence=_confidence(lines))
            page.heading_sizes[block.id] = max(l.size for l in lines) * (1.15 if kind == RegionKind.TITLE else 1.0)
            if kind == RegionKind.TITLE:
                block.role = "title"
            return [block]
        if kind == RegionKind.CAPTION:
            text = _join_lines(lines)
            if not text:
                return []
            if region.label in ("figure_title", "table_title") or len(text) <= 80:
                return [self._block(BlockType.CAPTION, text, region.box, confidence=_confidence(lines))]
            kind = RegionKind.TEXT  # long "notes" under a table are ordinary text

        one_per_line = kind == RegionKind.CONTENTS
        btype = {RegionKind.FOOTNOTE: BlockType.FOOTNOTE, RegionKind.ASIDE: BlockType.ASIDE}.get(kind, BlockType.PARAGRAPH)
        # Notes set small at the foot of the page, each opening with a number or mark.
        if btype == BlockType.PARAGRAPH and page.body_sizes and region.y0 > 0.72 * self.page_height:
            sizes = [w.size for w in words if not w.blank]
            if sizes and statistics.median(sizes) < 0.88 * statistics.median(page.body_sizes) \
                    and FOOTNOTE_START_RE.match(_join_lines(group_lines(words))):
                btype = BlockType.FOOTNOTE
        blocks: List[Block] = []
        for column in split_columns(words):
            col_lines = group_lines(column, split_gap=8.0)
            for part in line_columns(col_lines):
                blocks.extend(self._items(part, btype, one_per_line, page))
        return blocks

    def _items(self, lines: List[TextLine], btype: BlockType, one_per_line: bool,
               page: AssembledPage) -> List[Block]:
        if not lines:
            return []
        items = split_items(lines, one_per_line=one_per_line)
        base_x0 = statistics.median(l.x0 for l in lines) if len(lines) > 2 else min(l.x0 for l in lines)
        base_x0 = min(base_x0, min(item[0].x0 for item in items))
        blocks: List[Block] = []
        for item in items:
            text, styles = compose(item)
            if not text:
                continue
            marker_match = MARKER_RE.match(text)
            marker = marker_match.group(0).strip() if marker_match else None
            item_type = btype
            role = "contents" if one_per_line else None
            if marker and btype == BlockType.PARAGRAPH and not one_per_line:
                item_type = BlockType.LIST
                if DIALOGUE_RE.match(text):
                    role = "dialogue"
            size = statistics.median(l.size for l in item)
            # A short bold line alone in a text region is a run-in heading ("Exercises", "16.1 Fill the gaps...").
            lettered = [w for l in item for w in l.words if not w.blank and any(c.isalpha() for c in w.text)]
            fully_bold = bool(lettered) and all(w.bold for w in lettered)
            plain_number = bool(marker) and marker.rstrip(".)").isdigit() and "." not in marker.rstrip(".")
            if plain_number and page.body_sizes and size >= 1.15 * statistics.median(page.body_sizes):
                plain_number = False  # "1. Scope of review" set larger than the text is a numbered heading
            if (item_type in (BlockType.PARAGRAPH, BlockType.LIST) and len(item) <= 2 and fully_bold
                    and not plain_number and len(text) < 160 and not text.endswith((",", ";"))):
                block = self._block(BlockType.HEADING, text, union_box([l.box for l in item]), level=3,
                                    confidence=_confidence(item))
                page.heading_sizes[block.id] = size
                blocks.append(block)
                continue
            indent = _indent_level(item[0].x0, base_x0, size)
            previous = blocks[-1] if blocks else None
            if role == "dialogue" and previous is not None and previous.list_marker and previous.list_marker[0].isdigit():
                indent = max(indent, 1)  # B's reply lines up with A's line in a numbered exchange
            speaker = SPEAKER_AFTER_NUMBER_RE.match(text)
            if speaker:
                styles = styles + [InlineStyle(start=speaker.start(1), end=speaker.end(1), bold=True)]
            block = self._block(item_type, text, union_box([l.box for l in item]),
                                confidence=_confidence(item),
                                list_marker=marker if item_type == BlockType.LIST else None,
                                indent_level=indent, role=role, styles=styles)
            blocks.append(block)
        return blocks


def assign_heading_levels(blocks: List[Block], heading_sizes: Dict[str, float], body_size: float) -> None:
    """Consistent heading levels across the whole document (largest type = level 1)."""
    for block in blocks:
        size = heading_sizes.get(block.id)
        if size is None:
            continue
        if block.role == "title" or size >= 1.7 * body_size:
            block.level = 1
        elif size >= 1.2 * body_size:
            block.level = 2
        else:
            block.level = 3
