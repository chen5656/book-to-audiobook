import gc
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from src.loaders.epub_loader import _BLOCK_TAGS, _block_text


@dataclass
class Chapter:
    index: int
    title: str
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


def _items_in_reading_order(book) -> List:
    """Document items in spine (reading) order; manifest order can be scrambled."""
    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    by_id = {item.get_id(): item for item in docs}
    ordered, seen = [], set()
    for entry in book.spine:
        idref = entry[0] if isinstance(entry, tuple) else entry
        item = by_id.get(idref)
        if item is not None and idref not in seen:
            ordered.append(item)
            seen.add(idref)
    # keep any documents not listed in the spine, at the end
    ordered.extend(item for item in docs if item.get_id() not in seen)
    return ordered


def load_epub_chapters(path: str) -> List[Chapter]:
    """
    Loads an EPUB file and splits it into chapters based on HTML document items and headings.
    Frees BeautifulSoup DOM trees immediately to keep RAM usage minimal.
    """
    book = epub.read_epub(path)
    chapters: List[Chapter] = []
    chapter_idx = 1

    for item in _items_in_reading_order(book):
        soup = BeautifulSoup(item.get_body_content(), "html.parser")
        try:
            for span in soup.find_all("span"):
                if span.find("a"):
                    span.decompose()

            blocks = []
            heading_title = ""
            for block in soup.find_all(_BLOCK_TAGS):
                if block.find(_BLOCK_TAGS):
                    continue
                bt = _block_text(block)
                if bt:
                    if not heading_title and block.name in ("h1", "h2", "h3", "h4"):
                        heading_title = bt
                    blocks.append(bt)

            if not blocks:
                continue

            text_content = "\n\n".join(blocks)
            if len(text_content.strip()) < 30 and not heading_title:
                continue

            title = heading_title or f"Chapter {chapter_idx}"
            first_line = blocks[0].split("\n")[0].strip()
            if re.match(r"^(第[0-9一二三四五六七八九十百千万\d]+[章回]|\s*Chapter\s+\d+)", first_line):
                title = first_line

            chapters.append(Chapter(index=chapter_idx, title=title, text=text_content))
            chapter_idx += 1
        finally:
            soup.decompose()

    gc.collect()
    return chapters


def load_txt_chapters(path: str) -> List[Chapter]:
    """
    Loads a TXT file and splits it into chapters using standard chapter regex patterns.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    pattern = r"\n(?=(?:第[0-9一二三四五六七八九十百千万\d]+[章回]|\s*Chapter\s+\d+))"
    raw_chapters = re.split(pattern, content)
    raw_chapters = [c.strip() for c in raw_chapters if c.strip()]

    chapters: List[Chapter] = []
    for idx, raw in enumerate(raw_chapters, start=1):
        lines = raw.split("\n")
        title = lines[0].strip() if lines else f"Chapter {idx}"
        chapters.append(Chapter(index=idx, title=title, text=raw))

    return chapters


def load_chapters(path: str) -> List[Chapter]:
    """
    Dispatches file loading to EPUB or TXT chapter loader based on file extension.
    """
    ext = Path(path).suffix.lower()
    if ext == ".epub":
        return load_epub_chapters(path)
    elif ext in (".txt", ".text"):
        return load_txt_chapters(path)
    else:
        raise ValueError(f"Unsupported chapter file extension: {ext}")
