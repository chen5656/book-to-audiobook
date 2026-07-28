import re
from pathlib import Path
from typing import Optional

from src.cleaning import clean_text
from src.loaders import load_book
from src.translate import translate as translate_text

CACHE_DIR = Path(".cache")


def _slug_for(book_path: str) -> str:
    stem = Path(book_path).stem
    return re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()


def cache_path_for(book_path: str) -> Path:
    return CACHE_DIR / f"{_slug_for(book_path)}.txt"


def translated_cache_path_for(book_path: str, start_char: int, end_char: int, target: str) -> Path:
    return CACHE_DIR / f"{_slug_for(book_path)}.{start_char}-{end_char}.{target}.txt"


def read_or_extract_raw(book_path: str, format: Optional[str] = None) -> str:
    cache_path = cache_path_for(book_path)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    text = load_book(book_path, format=format)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


def read_or_extract(book_path: str, format: Optional[str] = None) -> str:
    cleaned, _stats = clean_text(read_or_extract_raw(book_path, format=format))
    return cleaned


def read_or_translate(
    book_path: str,
    start_char: int,
    end_char: int,
    source: str,
    target: str,
    trimmed_text: str,
) -> str:
    cache_path = translated_cache_path_for(book_path, start_char, end_char, target)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    translated = translate_text(trimmed_text, source, target)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(translated, encoding="utf-8")
    return translated