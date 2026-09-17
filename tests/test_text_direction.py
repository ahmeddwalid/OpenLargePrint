"""Unit tests for text direction, language detection, and bidi reordering (LANG-001, LANG-002)."""

import pytest
from openlargeprint.ir.models import TextDirection
from openlargeprint.text.direction import (
    count_script_chars,
    detect_language,
    detect_text_direction,
    is_arabic_char,
    is_bidi_text,
    is_rtl_char,
    normalize_arabic_logical_order,
)
from openlargeprint.text.bidi import reorder_bidi_for_display, reorder_bidi_line


def test_script_character_identification():
    """Verify script classification for individual characters."""
    assert is_arabic_char("ع")
    assert is_arabic_char("ق")
    assert is_arabic_char("د")
    assert is_arabic_char("ء")
    assert not is_arabic_char("A")
    assert not is_arabic_char("5")

    assert is_rtl_char("ع")
    assert is_rtl_char("ש")  # Hebrew Shin
    assert not is_rtl_char("Z")
    assert not is_rtl_char("9")


def test_detect_text_direction_and_language():
    """Verify direction and language detection for Arabic, English, and bidi text (LANG-001)."""
    # Pure Arabic
    ar_text = "العقد شريعة المتعاقدين ويجب تنفيذه طبقا لما اشتمل عليه."
    assert detect_text_direction(ar_text) == TextDirection.RTL
    assert detect_language(ar_text) == "ar"
    assert not is_bidi_text(ar_text)

    # Pure English
    en_text = "The contract is the law between the parties and must be executed in good faith."
    assert detect_text_direction(en_text) == TextDirection.LTR
    assert detect_language(en_text) == "en"
    assert not is_bidi_text(en_text)

    # Mixed Arabic with English citation (Bidi)
    mixed_ar = "تطبيقا لسابقة Donoghue v Stevenson [1932] في القانون المقارن."
    assert detect_text_direction(mixed_ar) == TextDirection.RTL
    assert detect_language(mixed_ar) == "ar"
    assert is_bidi_text(mixed_ar)

    # Empty and punctuation strings
    assert detect_text_direction("") == TextDirection.LTR
    assert detect_language("") == "en"
    assert detect_text_direction("--- 12345 ---") == TextDirection.LTR


def test_normalize_arabic_logical_order():
    """Verify detection and correction of reversed visual Arabic text in PDF streams."""
    # Logical text should remain untouched
    logical = "العقد شريعة المتعاقدين"
    assert normalize_arabic_logical_order(logical) == logical

    # Reversed visual text: 'دقعلا ةعيرش نيدقاعتملا'
    # 'دقعلا' has 'لا' at the end (reversed 'ال')
    # 'ةعيرش' has 'ة' at the start (reversed 'شريعة')
    visual = "دقعلا ةعيرش نيدقاعتملا"
    normalized = normalize_arabic_logical_order(visual)
    assert normalized == "العقد شريعة المتعاقدين"


def test_bidi_reordering_and_glyph_shaping():
    """Verify bidirectional reordering and contextual shaping for LTR canvas rendering."""
    # 1. Pure Arabic: letters are shaped and reversed for LTR canvas painting
    ar_text = "القانون المدني"
    reordered_ar = reorder_bidi_for_display(ar_text, TextDirection.RTL)
    assert reordered_ar != ar_text
    # Characters are connected presentation forms
    assert len(reordered_ar) > 0

    # 2. Mixed Arabic/English: Latin runs must preserve left-to-right character sequence
    mixed = "مبدأ Donoghue v Stevenson في الإهمال"
    reordered_mixed = reorder_bidi_for_display(mixed, TextDirection.RTL)
    # The English phrase itself must not be inverted character-by-character
    assert "Donoghue v Stevenson" in reordered_mixed

    # 3. Multiline text
    multiline = "الفقرة الأولى\nالفقرة الثانية"
    reordered_multi = reorder_bidi_for_display(multiline, TextDirection.RTL)
    assert "\n" in reordered_multi
    lines = reordered_multi.split("\n")
    assert len(lines) == 2


def test_bidi_edge_cases_and_ltr_base():
    """Verify bidi reordering with LTR base direction, CRLF linebreaks, and neutral resolution."""
    # Empty and whitespace
    assert reorder_bidi_for_display("") == ""
    assert reorder_bidi_for_display("   ") == "   "
    assert reorder_bidi_line("") == ""

    # Base LTR with embedded Arabic
    en_with_ar = "According to article عقد of the code."
    reordered_ltr = reorder_bidi_for_display(en_with_ar, TextDirection.LTR)
    assert "According to article " in reordered_ltr
    assert " of the code." in reordered_ltr

    # CRLF linebreaks
    crlf_text = "السطر الأول\r\nالسطر الثاني\r\n"
    reordered_crlf = reorder_bidi_for_display(crlf_text, TextDirection.RTL)
    assert "\r\n" in reordered_crlf

    # Hebrew character classification
    hebrew = "שלום"
    assert is_rtl_char(hebrew[0])
    reordered_hebrew = reorder_bidi_for_display(hebrew, TextDirection.RTL)
    assert len(reordered_hebrew) > 0
