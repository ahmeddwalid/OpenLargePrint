"""Bidirectional text reordering and Arabic glyph shaping (LANG-001, LANG-002)."""

from __future__ import annotations

import unicodedata
import arabic_reshaper
from openlargeprint.ir.models import TextDirection
from .direction import is_arabic_char, is_rtl_char


def _get_char_direction(char: str) -> str:
    """Classify character into RTL, LTR, WS (whitespace), or NEUTRAL."""
    if char in (" ", "\t"):
        return "WS"
    if is_arabic_char(char):
        return "RTL"
    bidi_type = unicodedata.bidirectional(char)
    if bidi_type in ("R", "AL"):
        return "RTL"
    if bidi_type in ("L", "EN"):
        return "LTR"
    return "NEUTRAL"


def reorder_bidi_line(line: str, base_direction: TextDirection = TextDirection.RTL) -> str:
    """Reorder a single line containing mixed Arabic and Latin scripts for LTR display."""
    if not line or not line.strip():
        return line

    # 1. OpenType contextual shaping of Arabic characters
    reshaped = arabic_reshaper.reshape(line)

    # 2. Segment into raw directional runs
    raw_runs: list[tuple[str, str]] = []
    curr_chars: list[str] = []
    curr_dir: str | None = None

    for char in reshaped:
        d = _get_char_direction(char)
        if curr_dir is None:
            curr_dir = d
            curr_chars.append(char)
        elif d == curr_dir:
            curr_chars.append(char)
        else:
            raw_runs.append(("".join(curr_chars), curr_dir))
            curr_chars = [char]
            curr_dir = d

    if curr_chars:
        raw_runs.append(("".join(curr_chars), curr_dir or "NEUTRAL"))

    # 3. Resolve whitespace and neutrals:
    # A space or neutral between two runs of the same direction takes that direction.
    base_dir_str = "RTL" if base_direction == TextDirection.RTL else "LTR"
    resolved_runs: list[tuple[str, str]] = []
    for idx, (content, r_dir) in enumerate(raw_runs):
        if r_dir in ("WS", "NEUTRAL"):
            prev_dir = resolved_runs[-1][1] if resolved_runs else None
            next_dir = raw_runs[idx + 1][1] if idx + 1 < len(raw_runs) else None
            if prev_dir and next_dir and prev_dir == next_dir and prev_dir in ("RTL", "LTR"):
                resolved_runs.append((content, prev_dir))
            else:
                resolved_runs.append((content, base_dir_str))
        else:
            resolved_runs.append((content, r_dir))

    # Merge adjacent runs with matching directionality
    merged_runs: list[tuple[str, str]] = []
    for content, r_dir in resolved_runs:
        if merged_runs and merged_runs[-1][1] == r_dir:
            merged_runs[-1] = (merged_runs[-1][0] + content, r_dir)
        else:
            merged_runs.append((content, r_dir))

    # 4. Form visual representation for LTR canvas painting
    # In LTR canvas:
    # - RTL runs have their character order reversed
    # - LTR runs retain internal character order
    # - If base_direction is RTL, sequence of runs is reversed (first logical run appears on the right)
    formatted_runs: list[str] = []
    for content, r_dir in merged_runs:
        if r_dir == "RTL":
            formatted_runs.append(content[::-1])
        else:
            formatted_runs.append(content)

    if base_direction == TextDirection.RTL:
        return "".join(reversed(formatted_runs))
    else:
        return "".join(formatted_runs)


def reorder_bidi_for_display(
    text: str, base_direction: TextDirection = TextDirection.RTL
) -> str:
    """Perform contextual glyph shaping and bidirectional reordering for visual rendering.
    
    Transforms logical Arabic/bidi text into visual glyph sequence suitable for
    engines that paint left-to-right without built-in OpenType shaping (e.g. ReportLab).
    """
    if not text:
        return text

    # Process line by line to preserve explicit linebreaks
    lines = text.splitlines(keepends=True)
    reordered_lines: list[str] = []

    for line in lines:
        newline_suffix = ""
        if line.endswith("\r\n"):
            newline_suffix = "\r\n"
            content = line[:-2]
        elif line.endswith("\n"):
            newline_suffix = "\n"
            content = line[:-1]
        else:
            content = line

        reordered = reorder_bidi_line(content, base_direction=base_direction)
        reordered_lines.append(reordered + newline_suffix)

    return "".join(reordered_lines)
