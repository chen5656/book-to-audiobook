import re

_DECORATIVE_LINE = re.compile(
    r"^[^\S\n]*(\S)(?:[^\S\n]*\1){2,}[^\S\n]*(?:\n|\Z)", re.MULTILINE
)

_ROMAN_CHAPTER = re.compile(
    r"^([^\S\n]*)(CHAPTER|CAP[IÍ]TULO)(\s+)([IVXLCDM]+)\b",
    re.IGNORECASE | re.MULTILINE,
)

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(token: str) -> int:
    values = [_ROMAN_VALUES[ch] for ch in token.upper()]
    total = 0
    for i, value in enumerate(values):
        if i + 1 < len(values) and value < values[i + 1]:
            total -= value
        else:
            total += value
    return total


def strip_decorative_lines(text: str) -> tuple:
    removed = len(_DECORATIVE_LINE.findall(text))
    cleaned = _DECORATIVE_LINE.sub("", text)
    return cleaned, removed


def normalize_roman_chapter_numbers(text: str) -> tuple:
    converted = 0

    def _replace(match: re.Match) -> str:
        nonlocal converted
        converted += 1
        leading, keyword, spacing, numeral = match.groups()
        return f"{leading}{keyword}{spacing}{roman_to_int(numeral)}"

    cleaned = _ROMAN_CHAPTER.sub(_replace, text)
    return cleaned, converted


def clean_text(text: str) -> tuple:
    cleaned, decorative_lines_removed = strip_decorative_lines(text)
    cleaned, roman_chapters_converted = normalize_roman_chapter_numbers(cleaned)
    stats = {
        "decorative_lines_removed": decorative_lines_removed,
        "roman_chapters_converted": roman_chapters_converted,
    }
    return cleaned, stats
