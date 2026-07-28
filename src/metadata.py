from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ebooklib import epub

from src.text_cache import read_or_extract


@dataclass
class BookMetadata:
    title: Optional[str]
    author: Optional[str]
    subtitle: Optional[str]


def extract_title_author(path: str, format: Optional[str] = None) -> BookMetadata:
    fmt = (format or Path(path).suffix).lstrip(".").lower()
    if fmt == "epub":
        return _extract_from_epub(path)
    return _extract_from_text(path, fmt)


def _extract_from_epub(path: str) -> BookMetadata:
    book = epub.read_epub(path)
    titles = book.get_metadata("DC", "title")
    creators = book.get_metadata("DC", "creator")

    title = titles[0][0] if titles else None
    author = creators[0][0] if creators else None
    subtitle = titles[1][0] if len(titles) > 1 else None

    return BookMetadata(title=title, author=author, subtitle=subtitle)


def _extract_from_text(path: str, fmt: str) -> BookMetadata:
    text = read_or_extract(path, format=fmt)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else None

    return BookMetadata(title=title, author=None, subtitle=None)