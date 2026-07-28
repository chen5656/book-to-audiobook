import re

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

_BLOCK_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "li", "pre", "blockquote", "div", "td", "th", "dd", "dt",
]

_BR_MARKER = "\x00"


def _block_text(tag) -> str:
    for br in tag.find_all("br"):
        br.replace_with(_BR_MARKER)
    text = tag.get_text()
    if tag.name == "pre":
        return text.strip("\n")
    # Source XHTML is hard-wrapped at a fixed column for readability; those
    # newlines aren't real breaks and would make edge-tts pause mid-sentence.
    # Only a <br/> (now the marker) is an intentional line break.
    text = re.sub(r"\s+", " ", text)
    text = re.sub(rf"\s*{_BR_MARKER}\s*", _BR_MARKER, text)
    return text.replace(_BR_MARKER, "\n").strip()


def load_epub(path: str) -> str:
    book = epub.read_epub(path)

    paragraphs = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_body_content(), "html.parser")
        for span in soup.find_all("span"):
            if span.find("a"):
                span.decompose()
        for block in soup.find_all(_BLOCK_TAGS):
            if block.find(_BLOCK_TAGS):
                continue  # not a leaf block; its text belongs to nested blocks
            block_text = _block_text(block)
            if block_text:
                paragraphs.append(block_text)

    return "\n\n".join(paragraphs)