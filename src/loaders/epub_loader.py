import re

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub


def load_epub(path: str) -> str:
    book = epub.read_epub(path)

    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_body_content(), "html.parser")
        for span in soup.find_all("span"):
            if span.find("a"):
                span.decompose()
        parts.append(soup.get_text())

    text = "".join(parts)
    return re.sub(r"\n+", "\n", text)