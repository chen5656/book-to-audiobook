from pathlib import Path
from typing import Optional

from src.loaders.epub_loader import load_epub
from src.loaders.pdf_loader import load_pdf
from src.loaders.txt_loader import load_txt

_LOADERS = {
    "epub": load_epub,
    "pdf": load_pdf,
    "txt": load_txt,
}


def load_book(path: str, format: Optional[str] = None) -> str:
    key = (format or Path(path).suffix).lstrip(".").lower()
    try:
        loader = _LOADERS[key]
    except KeyError:
        raise ValueError(
            f"Unsupported book format: {key!r}. Supported: {sorted(_LOADERS)}"
        )
    return loader(path)