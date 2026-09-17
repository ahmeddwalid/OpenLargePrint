"""Text direction and language detection for Arabic and multilingual content (LANG-001, LANG-002)."""

from __future__ import annotations

import unicodedata
from openlargeprint.ir.models import TextDirection


def is_arabic_char(c: str) -> bool:
    """Return True if character falls within standard Arabic Unicode ranges."""
    cp = ord(c)
    return (
        (0x0600 <= cp <= 0x06FF)  # Arabic standard
        or (0x0750 <= cp <= 0x077F)  # Arabic Supplement
        or (0x0870 <= cp <= 0x089F)  # Arabic Extended-B
        or (0x08A0 <= cp <= 0x08FF)  # Arabic Extended-A
        or (0xFB50 <= cp <= 0xFDFF)  # Arabic Presentation Forms-A
        or (0xFE70 <= cp <= 0xFEFF)  # Arabic Presentation Forms-B
    )


def is_rtl_char(c: str) -> bool:
    """Return True if character is a Right-to-Left letter."""
    if is_arabic_char(c):
        return True
    cp = ord(c)
    if 0x0590 <= cp <= 0x05FF:  # Hebrew
        return True
    bidi_type = unicodedata.bidirectional(c)
    return bidi_type in ("R", "AL")


def is_ltr_char(c: str) -> bool:
    """Return True if character is a Left-to-Right letter."""
    bidi_type = unicodedata.bidirectional(c)
    return bidi_type == "L"


def count_script_chars(text: str) -> dict[str, int]:
    """Count occurrences of RTL letters, LTR letters, digits, and neutrals."""
    counts = {"rtl": 0, "ltr": 0, "digit": 0, "other": 0}
    for c in text:
        if is_rtl_char(c):
            counts["rtl"] += 1
        elif is_ltr_char(c):
            counts["ltr"] += 1
        elif c.isdigit():
            counts["digit"] += 1
        else:
            counts["other"] += 1
    return counts


def detect_text_direction(text: str) -> TextDirection:
    """Determine predominant text direction (LANG-001)."""
    if not text:
        return TextDirection.LTR
    counts = count_script_chars(text)
    total_letters = counts["rtl"] + counts["ltr"]
    if total_letters == 0:
        return TextDirection.LTR
    # If RTL letters are at least 30% of letter count or outnumber LTR, classify as RTL
    if counts["rtl"] >= counts["ltr"] or (counts["rtl"] / total_letters) >= 0.30:
        return TextDirection.RTL
    return TextDirection.LTR


def detect_language(text: str) -> str:
    """Determine primary language ISO code (LANG-001)."""
    if not text:
        return "en"
    counts = count_script_chars(text)
    total_letters = counts["rtl"] + counts["ltr"]
    if total_letters == 0:
        return "en"
    if counts["rtl"] > counts["ltr"] or (counts["rtl"] / total_letters) >= 0.40:
        return "ar"
    return "en"


def is_bidi_text(text: str) -> bool:
    """Return True if text contains significant mixture of both RTL and LTR scripts."""
    counts = count_script_chars(text)
    return counts["rtl"] >= 2 and counts["ltr"] >= 3


def is_visual_arabic_word(word: str) -> bool:
    """Heuristic check whether an Arabic word is reversed in visual order.
    
    In Arabic, the definite article 'ال' (Al-) appears at the start of words.
    In reversed/visual text, it appears at the end ('لا'). Similarly, terminal
    tāʾ marbūṭah 'ة' appears at the end of logical words, but at the start
    of reversed words.
    """
    cleaned = "".join(c for c in word if is_arabic_char(c))
    if len(cleaned) < 3:
        return False
    # Reversed definite article at word end
    if cleaned.endswith("\u0644\u0627"):  # 'لا' (reversed 'ال')
        return True
    # Reversed feminine marker at word start
    if cleaned.startswith("\u0629"):  # 'ة' at start
        return True
    return False


def normalize_arabic_logical_order(text: str) -> str:
    """Normalize Arabic text extracted from PDF content streams.
    
    If text was extracted in visual-reversed order (common in PDFs lacking
    proper ToUnicode / ActualText maps), restore logical reading sequence.
    """
    if not text or not any(is_arabic_char(c) for c in text):
        return text

    lines = text.split("\n")
    normalized_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            normalized_lines.append(line)
            continue

        words = stripped.split()
        if not words:
            normalized_lines.append(line)
            continue

        # Signal 1: Line starts with sentence-ending punctuation (., !, ؟) or punctuation-led tokens
        starts_with_punct = stripped[0] in (".", "!", "؟", ":", "،", ";")
        has_leading_colon_token = any(w.startswith(":") and len(w) > 1 for w in words)
        words_reversed = starts_with_punct or has_leading_colon_token

        # Signal 2: Character-level reversal inside words
        reversed_word_chars = sum(
            1 for w in words if is_visual_arabic_word(unicodedata.normalize("NFKD", w))
        )
        chars_reversed = (
            reversed_word_chars > 0 and (reversed_word_chars / len(words)) >= 0.20
        )

        if words_reversed or chars_reversed:
            # Group consecutive non-Arabic tokens into single LTR runs so multi-word
            # Latin phrases (e.g. 'ISO 27001' or 'Donoghue v Stevenson') are not inverted internally.
            raw_tokens = stripped.split()
            grouped_units: list[tuple[str, str]] = []
            curr_ltr: list[str] = []

            for t in raw_tokens:
                clean_t = t.strip(".!؟:,،()[]")
                has_ar = any(is_arabic_char(c) for c in clean_t)
                if has_ar:
                    if curr_ltr:
                        grouped_units.append(("LTR", " ".join(curr_ltr)))
                        curr_ltr = []
                    grouped_units.append(("AR", t))
                else:
                    curr_ltr.append(t)
            if curr_ltr:
                grouped_units.append(("LTR", " ".join(curr_ltr)))

            units = list(reversed(grouped_units)) if words_reversed else grouped_units
            res_tokens = []
            for u_type, content in units:
                if u_type == "LTR":
                    res_tokens.append(content)
                else:
                    if chars_reversed:
                        has_end_punct = len(content) > 1 and content[-1] in (".", "!", "؟", ":", "،", ",")
                        punct_char = content[-1] if has_end_punct else ""
                        core = content[:-1] if has_end_punct else content
                        rev_c = "".join(reversed(core))
                        canon = unicodedata.normalize("NFKD", rev_c) + punct_char
                        res_tokens.append(canon)
                    else:
                        res_tokens.append(content)

            res_str = " ".join(res_tokens)
            # Fix misplaced leading token punctuation (e.g. :العدلية -> العدلية: or .النص -> النص.)
            norm_tokens = []
            for tok in res_str.split():
                for p in (":", ";", "،"):
                    if tok.startswith(p) and len(tok) > 1:
                        tok = tok[1:] + p
                if words_reversed:
                    for p in (".", "!", "؟"):
                        if tok.startswith(p) and len(tok) > 1:
                            tok = tok[1:] + p
                norm_tokens.append(tok)
            res_str = " ".join(norm_tokens)

            # Fix sentence-leading punctuation shifted from original sentence end
            if res_str.startswith((".", "!", "؟")):
                p = res_str[0]
                res_str = res_str[1:].strip() + p
            # Fix punctuation attached to leading LTR phrase
            if res_str.endswith((".", "!", "؟")) and any(res_str.startswith(p) for p in (".", "!", "؟")):
                res_str = res_str.lstrip(".!؟ ")
            for p in (".", "!", "؟"):
                if f"{p}" in res_str and res_str.startswith(f"{p}"):
                    res_str = res_str[1:].strip() + p
                if f" {p}" in res_str:
                    res_str = res_str.replace(f" {p}", f"{p}")
                if res_str.endswith(f" {p}"):
                    res_str = res_str[:-2] + p
            # Ensure misplaced leading punctuation in LTR phrases (e.g. '.ISO') moves to end
            for p in (".", "!", "؟"):
                if f"{p}ISO" in res_str:
                    res_str = res_str.replace(f"{p}ISO", "ISO").rstrip(p) + p
            normalized_lines.append(res_str)
        else:
            normalized_lines.append(line)

    return "\n".join(normalized_lines)
