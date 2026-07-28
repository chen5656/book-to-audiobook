import pytest

from src.cleaning import (
    clean_text,
    normalize_roman_chapter_numbers,
    roman_to_int,
    strip_decorative_lines,
)


def test_strip_decorative_lines_removes_asterisk_scene_break():
    text = (
        "She was silent for a moment.\n"
        "*      *      *      *      *      *      *\n"
        "It was quite silent by now.\n"
    )

    cleaned, removed = strip_decorative_lines(text)

    assert "*      *" not in cleaned
    assert "She was silent for a moment." in cleaned
    assert "It was quite silent by now." in cleaned
    assert removed == 1


def test_strip_decorative_lines_handles_nbsp_separator_from_epub_extraction():
    # BeautifulSoup renders &nbsp; as U+00A0, not a regular space - this is
    # the real separator found in EPUB-extracted scene breaks.
    line = "*\xa0\xa0\xa0\xa0\xa0\xa0*\xa0\xa0\xa0\xa0\xa0\xa0*\xa0\xa0\xa0\xa0\xa0\xa0*"
    text = f"Prose before.\n{line}\nProse after.\n"

    cleaned, removed = strip_decorative_lines(text)

    assert line not in cleaned
    assert removed == 1


def test_strip_decorative_lines_generalizes_beyond_asterisk():
    for line in ["-----", "~ ~ ~", "======"]:
        text = f"Prose before.\n{line}\nProse after.\n"

        cleaned, removed = strip_decorative_lines(text)

        assert line not in cleaned
        assert removed == 1


def test_strip_decorative_lines_leaves_normal_prose_untouched():
    text = "This is a perfectly normal sentence.\n"

    cleaned, removed = strip_decorative_lines(text)

    assert cleaned == text
    assert removed == 0


def test_strip_decorative_lines_requires_at_least_three_repeats():
    text = "Prose before.\n--\nProse after.\n"

    cleaned, removed = strip_decorative_lines(text)

    assert "--" in cleaned
    assert removed == 0


def test_strip_decorative_lines_ignores_mixed_symbols():
    text = "Prose before.\n* - * - *\nProse after.\n"

    cleaned, removed = strip_decorative_lines(text)

    assert "* - * - *" in cleaned
    assert removed == 0


@pytest.mark.parametrize("token,value", [
    ("I", 1), ("IV", 4), ("IX", 9), ("XII", 12), ("XL", 40), ("MCMXCIX", 1999),
])
def test_roman_to_int_parses_standard_numerals(token, value):
    assert roman_to_int(token) == value


def test_normalize_roman_chapter_numbers_tolerates_leading_whitespace():
    # Real EPUB table-of-contents entries come out of BeautifulSoup with a
    # leading space before the keyword, e.g. "\n CHAPTER IV".
    text = " CHAPTER IV\nThe Rabbit Sends in a Little Bill\n"

    cleaned, converted = normalize_roman_chapter_numbers(text)

    assert " CHAPTER 4" in cleaned
    assert converted == 1


def test_normalize_roman_chapter_numbers_converts_english_heading():
    text = "CHAPTER IV.The Rabbit Sends in a Little Bill\n"

    cleaned, converted = normalize_roman_chapter_numbers(text)

    assert cleaned.startswith("CHAPTER 4.")
    assert converted == 1


def test_normalize_roman_chapter_numbers_converts_portuguese_heading():
    text = "CAPÍTULO XII\nAlice's Evidence\n"

    cleaned, converted = normalize_roman_chapter_numbers(text)

    assert "CAPÍTULO 12" in cleaned
    assert converted == 1


def test_normalize_roman_chapter_numbers_is_case_insensitive():
    text = "chapter ix\nThe Mock Turtle's Story\n"

    cleaned, converted = normalize_roman_chapter_numbers(text)

    assert "chapter 9" in cleaned
    assert converted == 1


def test_normalize_roman_chapter_numbers_leaves_arabic_numbers_unchanged():
    text = "CHAPTER 3\nAlready arabic.\n"

    cleaned, converted = normalize_roman_chapter_numbers(text)

    assert cleaned == text
    assert converted == 0


def test_normalize_roman_chapter_numbers_does_not_touch_unrelated_text():
    text = "MIX the batter well before baking.\n"

    cleaned, converted = normalize_roman_chapter_numbers(text)

    assert cleaned == text
    assert converted == 0


def test_clean_text_applies_both_passes_and_reports_stats():
    text = (
        "CHAPTER IV.The Rabbit Sends in a Little Bill\n"
        "Some prose.\n"
        "*      *      *      *      *      *      *\n"
        "More prose.\n"
    )

    cleaned, stats = clean_text(text)

    assert "CHAPTER 4." in cleaned
    assert "*      *" not in cleaned
    assert stats == {"decorative_lines_removed": 1, "roman_chapters_converted": 1}


def test_clean_text_is_idempotent():
    text = (
        "CHAPTER IV.The Rabbit Sends in a Little Bill\n"
        "*      *      *      *      *      *      *\n"
    )

    once, _ = clean_text(text)
    twice, stats_twice = clean_text(once)

    assert once == twice
    assert stats_twice == {"decorative_lines_removed": 0, "roman_chapters_converted": 0}
