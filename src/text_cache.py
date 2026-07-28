import re
from pathlib import Path
from typing import Optional

from src.loaders import load_book

CACHE_DIR = Path(".cache")


def cache_path_for(book_path: str) -> Path:
    stem = Path(book_path).stem
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return CACHE_DIR / f"{slug}.txt"


def read_or_extract(book_path: str, format: Optional[str] = None) -> str:
    cache_path = cache_path_for(book_path)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    text = load_book(book_path, format=format)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text