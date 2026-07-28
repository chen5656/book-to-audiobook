import re
from dataclasses import dataclass

PREVIEW_RADIUS = 100

KINDS = (
    "gutenberg_marker",
    "chapter_heading",
    "table_of_contents",
    "back_matter",
    "front_matter",
)


@dataclass
class BoundaryCandidate:
    char_offset: int
    kind: str
    matched_text: str
    preview: str


_PATTERNS = [
    ("gutenberg_marker", re.compile(
        r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
        re.IGNORECASE,
    )),
    ("gutenberg_marker", re.compile(
        r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
        re.IGNORECASE,
    )),
    ("chapter_heading", re.compile(
        r"^(CHAPTER|CAP[IÍ]TULO)\s+[IVXLCDM\d]+",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("table_of_contents", re.compile(
        r"^(TABLE OF CONTENTS|SUM[AÁ]RIO|[IÍ]NDICE)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("back_matter", re.compile(
        r"^(ACKNOWLEDGE?MENTS|AGRADECIMENTOS|ABOUT THE AUTHOR|SOBRE O AUTOR|"
        r"REFERENCES|BIBLIOGRAPHY|REFER[ÊE]NCIAS)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("front_matter", re.compile(
        r"^(PREFACE|PREF[ÁA]CIO|FOREWORD|DEDICATION|DEDICAT[ÓO]RIA|EPIGRAPH|"
        r"EP[ÍI]GRAFE|INTRODUCTION|INTRODU[ÇC][ÃA]O)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )),
]


def find_boundary_candidates(text: str) -> list:
    candidates = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            offset = match.start()
            start = max(0, offset - PREVIEW_RADIUS)
            end = min(len(text), offset + PREVIEW_RADIUS)
            candidates.append(BoundaryCandidate(
                char_offset=offset,
                kind=kind,
                matched_text=match.group(0),
                preview=text[start:end],
            ))
    candidates.sort(key=lambda c: c.char_offset)
    return candidates


def trim_to_boundaries(text: str, start_char: int, end_char: int) -> str:
    if start_char < 0 or end_char > len(text) or start_char >= end_char:
        raise ValueError(
            f"Invalid boundaries: start_char={start_char}, end_char={end_char}, "
            f"text length={len(text)}"
        )
    return text[start_char:end_char]