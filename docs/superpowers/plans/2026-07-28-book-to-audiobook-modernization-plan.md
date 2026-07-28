# Book-to-Audiobook Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the legacy manual "book → pt-BR audiobook" notebook pipeline into a tested `src/` library plus a Claude Code Skill/plugin, with no automatic content cuts (human confirms start/end boundaries) and no operational config in `.env`.

**Architecture:** Small single-responsibility modules under `src/` (loaders → text_cache → boundary/metadata/pronunciation → translate/intro/text_to_speech → pipeline orchestrator → cli), each unit-tested offline with synthetic fixtures (no real book text, no network calls). `cli.py` exposes `doctor | inspect | pronunciation | convert`, all driven by explicit flags. A Claude Code Skill (`SKILL.md` + `plugin.json`) wraps the CLI in a gated conversational flow.

**Tech Stack:** Python 3, `ebooklib` + `beautifulsoup4` (epub), `PyMuPDF`/`fitz` (pdf), `edge-tts` (TTS), `deep-translator` (translation), `pydub` (audio), `pytest` (tests), `argparse` (CLI).

**Sources:** [`docs/modernization-plan.md`](../../modernization-plan.md), [`docs/superpowers/specs/2026-07-28-book-to-audiobook-modernization-design.md`](../specs/2026-07-28-book-to-audiobook-modernization-design.md).

## Global Constraints

- No paid API keys anywhere; `edge-tts` and `deep-translator`'s `GoogleTranslator` stay free/keyless.
- Target machine has 8GB RAM — no ML/OCR models, no MinerU. Dependencies stay small.
- PDF loading uses **PyMuPDF only**. `PyPDF2` is removed from `requirements.txt`.
- HTML is **not** a supported loader format (dropped per plan — was a single-site crawler, not generic).
- No commercial book text in any test — fixtures are built programmatically in-test (synthetic epub/pdf/txt) or are public-domain.
- Operational config (voice, target language, file paths) is **never** read from `.env` — always explicit function args / CLI flags.
- `cli.py convert` requires `--start-char`/`--end-char` explicitly — no automatic content boundary detection ships without human confirmation.
- New module identifiers are in English (`load_book`, `find_boundary_candidates`, `split_into_sentences`, etc.). `tools.py` keeps its existing Portuguese names (plan says "mantido como está"); `translate.py`/`text_to_speech.py` only rename/change what's explicitly specified below.
- `BoundaryCandidate.kind` is a closed enum of exactly 5 values: `gutenberg_marker`, `chapter_heading`, `table_of_contents`, `back_matter`, `front_matter`.
- `flag_risky_tokens` `reason` is a closed enum of exactly 3 values: `acronym`, `number`, `foreign_name`.
- `inspect`/`pronunciation` extracted text is cached to `.cache/<slug>.txt` (already covered by the existing generic `.cache` line in `.gitignore` — verified, no `.gitignore` change needed).
- This plan covers only the `src/` library + Skill/plugin packaging. Repository restructuring (deleting `examples/`, `blog_post/`, git history reset) is explicitly out of scope — that's a separate, later, destructive step per `docs/modernization-plan.md`.

---

## Task 1: Test scaffolding + `txt_loader`

**Files:**
- Create: `pyproject.toml`
- Create: `requirements-dev.txt`
- Create: `src/loaders/txt_loader.py`
- Test: `tests/loaders/test_txt_loader.py`

**Interfaces:**
- Produces: `load_txt(path: str) -> str` — reads a UTF-8 text file and returns its full contents.

- [ ] **Step 1: Create pytest config**

Create `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create dev requirements**

Create `requirements-dev.txt`:

```
pytest>=7.4.0
```

- [ ] **Step 3: Write the failing test**

Create `tests/loaders/test_txt_loader.py`:

```python
from src.loaders.txt_loader import load_txt


def test_load_txt_returns_file_contents(tmp_path):
    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter 1\n\nHello world.", encoding="utf-8")

    result = load_txt(str(book_path))

    assert result == "Chapter 1\n\nHello world."
```

- [ ] **Step 4: Install dev dependencies and run test to verify it fails**

Run: `pip install -r requirements-dev.txt && pytest tests/loaders/test_txt_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.loaders'`

- [ ] **Step 5: Write minimal implementation**

Create `src/loaders/txt_loader.py`:

```python
def load_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/loaders/test_txt_loader.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml requirements-dev.txt src/loaders/txt_loader.py tests/loaders/test_txt_loader.py
git commit -m "test: add pytest scaffolding and txt_loader"
```

---

## Task 2: `epub_loader`

**Files:**
- Create: `src/loaders/epub_loader.py`
- Test: `tests/loaders/test_epub_loader.py`

**Interfaces:**
- Consumes: `ebooklib.epub`, `bs4.BeautifulSoup` (third-party, already in `requirements.txt`).
- Produces: `load_epub(path: str) -> str` — concatenated text of every `ITEM_DOCUMENT` in the epub, with `<span>` elements that contain an `<a>` link stripped, and runs of blank lines collapsed to one `\n`.

- [ ] **Step 1: Write the failing test**

Create `tests/loaders/test_epub_loader.py`. This builds a tiny synthetic epub in-test with `ebooklib` — no real book file needed:

```python
import ebooklib
from ebooklib import epub

from src.loaders.epub_loader import load_epub


def _build_epub(tmp_path):
    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Test Author")

    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap1.xhtml", lang="en")
    chapter.content = (
        "<html><body>"
        "<p>Hello world.</p>"
        "<p>See <span><a href='#note1'>note 1</a></span> here.</p>"
        "</body></html>"
    )
    book.add_item(chapter)
    book.toc = (epub.Link("chap1.xhtml", "Chapter 1", "chap1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    path = tmp_path / "test.epub"
    epub.write_epub(str(path), book)
    return str(path)


def test_load_epub_strips_linked_spans_and_extracts_text(tmp_path):
    path = _build_epub(tmp_path)

    result = load_epub(path)

    assert "Hello world." in result
    assert "note 1" not in result


def test_load_epub_collapses_blank_line_runs(tmp_path):
    path = _build_epub(tmp_path)

    result = load_epub(path)

    assert "\n\n\n" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_epub_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.loaders.epub_loader'`

- [ ] **Step 3: Write minimal implementation**

Create `src/loaders/epub_loader.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_epub_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/loaders/epub_loader.py tests/loaders/test_epub_loader.py
git commit -m "feat: add epub_loader"
```

---

## Task 3: `pdf_loader` + drop `PyPDF2`

**Files:**
- Create: `src/loaders/pdf_loader.py`
- Modify: `requirements.txt` (remove `PyPDF2` line and its comment)
- Test: `tests/loaders/test_pdf_loader.py`

**Interfaces:**
- Consumes: `fitz` (PyMuPDF, already in `requirements.txt`).
- Produces: `load_pdf(path: str) -> str` — text of every page joined with `\n`, with a trailing page-number footer line stripped per page.

- [ ] **Step 1: Write the failing test**

Create `tests/loaders/test_pdf_loader.py`. Builds a tiny synthetic PDF in-test with `fitz` — no real book file needed:

```python
import fitz

from src.loaders.pdf_loader import load_pdf


def _build_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world.")
    page.insert_text((72, 700), "42")  # simulated page-number footer
    path = tmp_path / "test.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_load_pdf_extracts_text(tmp_path):
    path = _build_pdf(tmp_path)

    result = load_pdf(path)

    assert "Hello world." in result


def test_load_pdf_strips_trailing_page_number(tmp_path):
    path = _build_pdf(tmp_path)

    result = load_pdf(path)

    assert result.strip().splitlines()[-1] != "42"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_pdf_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.loaders.pdf_loader'`

- [ ] **Step 3: Write minimal implementation**

Create `src/loaders/pdf_loader.py`:

```python
import re

import fitz


def load_pdf(path: str) -> str:
    doc = fitz.open(path)
    pages = []
    for page in doc:
        text = page.get_text("text")
        text = re.sub(r"\n?\s*\d+\s*$", "", text)
        pages.append(text)
    doc.close()

    return "\n".join(pages).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_pdf_loader.py -v`
Expected: PASS

- [ ] **Step 5: Remove PyPDF2 from requirements.txt**

Edit `requirements.txt`: delete these two lines (the comment and the pin):

```
# Leitura de arquivos PDF
PyPDF2>=3.0.1
```

- [ ] **Step 6: Commit**

```bash
git add src/loaders/pdf_loader.py tests/loaders/test_pdf_loader.py requirements.txt
git commit -m "feat: add pdf_loader (PyMuPDF only), drop PyPDF2"
```

---

## Task 4: `load_book` dispatch

**Files:**
- Create: `src/loaders/__init__.py`
- Test: `tests/loaders/test_dispatch.py`

**Interfaces:**
- Consumes: `load_epub` (Task 2), `load_pdf` (Task 3), `load_txt` (Task 1).
- Produces: `load_book(path: str, format: Optional[str] = None) -> str` — picks the loader by `format` if given, else by the file's extension (case-insensitive, with or without leading dot); raises `ValueError` for unsupported formats.

- [ ] **Step 1: Write the failing test**

Create `tests/loaders/test_dispatch.py`:

```python
import pytest

from src.loaders import load_book


def test_load_book_dispatches_by_extension(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text("hello", encoding="utf-8")

    assert load_book(str(path)) == "hello"


def test_load_book_dispatches_by_explicit_format(tmp_path):
    path = tmp_path / "book.weird"
    path.write_text("hello", encoding="utf-8")

    assert load_book(str(path), format="txt") == "hello"


def test_load_book_unsupported_format_raises(tmp_path):
    path = tmp_path / "book.docx"
    path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        load_book(str(path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_dispatch.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_book'`

- [ ] **Step 3: Write minimal implementation**

Create `src/loaders/__init__.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_dispatch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/loaders/__init__.py tests/loaders/test_dispatch.py
git commit -m "feat: add load_book dispatch by format/extension"
```

---

## Task 5: `text_cache`

**Files:**
- Create: `src/text_cache.py`
- Test: `tests/test_text_cache.py`

**Interfaces:**
- Consumes: `load_book(path, format=None) -> str` (Task 4).
- Produces: `cache_path_for(book_path: str) -> Path` (`.cache/<slug>.txt`, deterministic from filename stem); `read_or_extract(book_path: str, format: Optional[str] = None) -> str` (reads cache if present, else calls `load_book` and writes cache).

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_cache.py`:

```python
from pathlib import Path

from src.text_cache import cache_path_for, read_or_extract


def test_cache_path_for_is_deterministic_slug(tmp_path):
    book_path = str(tmp_path / "My Book (2024).epub")

    result = cache_path_for(book_path)

    assert result == Path(".cache/my-book-2024.txt")


def test_read_or_extract_writes_and_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text("original content", encoding="utf-8")

    first = read_or_extract(str(book_path))
    assert first == "original content"
    assert cache_path_for(str(book_path)).exists()

    # Change the source file; cached read must NOT reprocess it.
    book_path.write_text("changed content", encoding="utf-8")
    second = read_or_extract(str(book_path))

    assert second == "original content"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_text_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.text_cache'`

- [ ] **Step 3: Write minimal implementation**

Create `src/text_cache.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_text_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/text_cache.py tests/test_text_cache.py
git commit -m "feat: add text_cache to avoid reprocessing books"
```

---

## Task 6: `boundary`

**Files:**
- Create: `src/boundary.py`
- Test: `tests/test_boundary.py`

**Interfaces:**
- Produces:
  - `BoundaryCandidate` dataclass: `char_offset: int`, `kind: str` (one of `gutenberg_marker`, `chapter_heading`, `table_of_contents`, `back_matter`, `front_matter`), `matched_text: str`, `preview: str`.
  - `find_boundary_candidates(text: str) -> list[BoundaryCandidate]` — sorted by `char_offset`; never modifies `text`.
  - `trim_to_boundaries(text: str, start_char: int, end_char: int) -> str` — raises `ValueError` if bounds are invalid.

- [ ] **Step 1: Write the failing test**

Create `tests/test_boundary.py`:

```python
import pytest

from src.boundary import find_boundary_candidates, trim_to_boundaries

GUTENBERG_TEXT = (
    "Some license header.\n"
    "*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***\n"
    "CHAPTER I\n"
    "It was a dark and stormy night.\n"
    "*** END OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***\n"
    "Some trailer.\n"
)

NO_MARKER_TEXT = (
    "All in the golden afternoon.\n"
    "A poem before the real content.\n"
    "CHAPTER I\n"
    "It was a dark and stormy night.\n"
    "ACKNOWLEDGMENTS\n"
    "Thanks to everyone.\n"
)


def test_find_boundary_candidates_detects_gutenberg_markers():
    candidates = find_boundary_candidates(GUTENBERG_TEXT)

    kinds = [c.kind for c in candidates]
    assert "gutenberg_marker" in kinds
    assert "chapter_heading" in kinds


def test_find_boundary_candidates_works_without_any_marker():
    candidates = find_boundary_candidates(NO_MARKER_TEXT)

    kinds = {c.kind for c in candidates}
    assert "gutenberg_marker" not in kinds
    assert "chapter_heading" in kinds
    assert "back_matter" in kinds


def test_find_boundary_candidates_detects_all_five_kinds():
    text = (
        "PREFACE\n"
        "A short preface before the story.\n"
        "TABLE OF CONTENTS\n"
        "Chapter I .......... 1\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK TEST BOOK ***\n"
        "CHAPTER I\n"
        "It was a dark and stormy night.\n"
        "ACKNOWLEDGMENTS\n"
        "Thanks to everyone.\n"
    )

    kinds = {c.kind for c in find_boundary_candidates(text)}

    assert kinds == {
        "front_matter", "table_of_contents", "gutenberg_marker",
        "chapter_heading", "back_matter",
    }


def test_find_boundary_candidates_are_sorted_by_offset():
    candidates = find_boundary_candidates(GUTENBERG_TEXT)

    offsets = [c.char_offset for c in candidates]
    assert offsets == sorted(offsets)


def test_find_boundary_candidates_preview_contains_matched_text():
    candidates = find_boundary_candidates(GUTENBERG_TEXT)

    for c in candidates:
        assert c.matched_text in c.preview or c.matched_text in GUTENBERG_TEXT


def test_trim_to_boundaries_cuts_text():
    text = "0123456789"

    assert trim_to_boundaries(text, 2, 5) == "234"


def test_trim_to_boundaries_rejects_invalid_range():
    text = "0123456789"

    with pytest.raises(ValueError):
        trim_to_boundaries(text, 5, 2)

    with pytest.raises(ValueError):
        trim_to_boundaries(text, -1, 5)

    with pytest.raises(ValueError):
        trim_to_boundaries(text, 0, 999)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_boundary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.boundary'`

- [ ] **Step 3: Write minimal implementation**

Create `src/boundary.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_boundary.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/boundary.py tests/test_boundary.py
git commit -m "feat: add boundary candidate detection and trimming"
```

---

## Task 7: `metadata`

**Files:**
- Create: `src/metadata.py`
- Test: `tests/test_metadata.py`

**Interfaces:**
- Consumes: `load_book` (Task 4), `ebooklib.epub`.
- Produces: `BookMetadata` dataclass (`title: Optional[str]`, `author: Optional[str]`, `subtitle: Optional[str]`); `extract_title_author(path: str, format: Optional[str] = None) -> BookMetadata`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_metadata.py`:

```python
from ebooklib import epub

from src.metadata import BookMetadata, extract_title_author


def _build_epub(tmp_path, title="Test Book", author="Test Author"):
    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap1.xhtml", lang="en")
    chapter.content = "<html><body><p>Hello world.</p></body></html>"
    book.add_item(chapter)
    book.toc = (epub.Link("chap1.xhtml", "Chapter 1", "chap1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    path = tmp_path / "test.epub"
    epub.write_epub(str(path), book)
    return str(path)


def test_extract_title_author_from_epub_metadata(tmp_path):
    path = _build_epub(tmp_path, title="Alice's Adventures in Wonderland", author="Lewis Carroll")

    result = extract_title_author(path)

    assert result == BookMetadata(
        title="Alice's Adventures in Wonderland",
        author="Lewis Carroll",
        subtitle=None,
    )


def test_extract_title_author_from_txt_uses_first_line(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text("My Book Title\n\nOnce upon a time...", encoding="utf-8")

    result = extract_title_author(str(path))

    assert result.title == "My Book Title"
    assert result.author is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metadata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.metadata'`

- [ ] **Step 3: Write minimal implementation**

Create `src/metadata.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ebooklib import epub

from src.loaders import load_book


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
    text = load_book(path, format=fmt)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else None

    return BookMetadata(title=title, author=None, subtitle=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_metadata.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/metadata.py tests/test_metadata.py
git commit -m "feat: add title/author/subtitle metadata extraction"
```

---

## Task 8: `intro`

**Files:**
- Create: `src/intro.py`
- Test: `tests/test_intro.py`

**Interfaces:**
- Consumes: `BookMetadata` (Task 7).
- Produces: `build_intro_text(metadata: BookMetadata) -> str`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_intro.py`:

```python
from src.intro import build_intro_text
from src.metadata import BookMetadata


def test_build_intro_text_with_title_subtitle_and_author():
    metadata = BookMetadata(
        title="Alice's Adventures in Wonderland",
        author="Lewis Carroll",
        subtitle="A tale of curious wonder",
    )

    result = build_intro_text(metadata)

    assert result == (
        "Alice's Adventures in Wonderland. A tale of curious wonder. "
        "De Lewis Carroll."
    )


def test_build_intro_text_with_only_title():
    metadata = BookMetadata(title="Alice's Adventures in Wonderland", author=None, subtitle=None)

    result = build_intro_text(metadata)

    assert result == "Alice's Adventures in Wonderland."


def test_build_intro_text_falls_back_when_title_missing():
    metadata = BookMetadata(title=None, author=None, subtitle=None)

    result = build_intro_text(metadata)

    assert result == "Audiobook."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_intro.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.intro'`

- [ ] **Step 3: Write minimal implementation**

Create `src/intro.py`:

```python
from src.metadata import BookMetadata


def build_intro_text(metadata: BookMetadata) -> str:
    parts = [metadata.title or "Audiobook"]
    if metadata.subtitle:
        parts.append(metadata.subtitle)

    intro = ". ".join(parts) + "."
    if metadata.author:
        intro += f" De {metadata.author}."

    return intro
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_intro.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/intro.py tests/test_intro.py
git commit -m "feat: add spoken intro text builder"
```

---

## Task 9: `pronunciation`

**Files:**
- Create: `src/pronunciation.py`
- Test: `tests/test_pronunciation.py`

**Interfaces:**
- Produces: `flag_risky_tokens(text: str) -> list[dict]` — each item is `{"token": str, "reason": "acronym"|"number"|"foreign_name", "char_offset": int, "context": str}`, sorted by `char_offset`. Never modifies `text`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pronunciation.py`:

```python
from src.pronunciation import flag_risky_tokens


def test_flags_acronym():
    text = "Her ISBN was printed on the back cover."

    flagged = flag_risky_tokens(text)

    acronyms = [f for f in flagged if f["reason"] == "acronym"]
    assert any(f["token"] == "ISBN" for f in acronyms)


def test_flags_number():
    text = "She was born in 1865 in England."

    flagged = flag_risky_tokens(text)

    numbers = [f for f in flagged if f["reason"] == "number"]
    assert any(f["token"] == "1865" for f in numbers)


def test_flags_mid_sentence_proper_noun_as_foreign_name():
    text = "The cat's name was Lacie, and everyone loved her."

    flagged = flag_risky_tokens(text)

    names = [f for f in flagged if f["reason"] == "foreign_name"]
    assert any(f["token"] == "Lacie" for f in names)


def test_does_not_flag_sentence_initial_capitalization():
    text = "Hello there. Another sentence starts here."

    flagged = flag_risky_tokens(text)

    names = [f for f in flagged if f["reason"] == "foreign_name"]
    assert not any(f["token"] in ("Hello", "Another") for f in names)


def test_flagged_tokens_are_sorted_by_offset():
    text = "ISBN 1865 Lacie"

    flagged = flag_risky_tokens(text)

    offsets = [f["char_offset"] for f in flagged]
    assert offsets == sorted(offsets)


def test_flagged_token_has_char_offset_and_context():
    text = "Her ISBN was printed on the back cover."

    flagged = flag_risky_tokens(text)

    isbn = next(f for f in flagged if f["token"] == "ISBN")
    assert text[isbn["char_offset"]:isbn["char_offset"] + len("ISBN")] == "ISBN"
    assert "ISBN" in isbn["context"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pronunciation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.pronunciation'`

- [ ] **Step 3: Write minimal implementation**

Create `src/pronunciation.py`:

```python
import re

CONTEXT_RADIUS = 40
_SENTENCE_END = (".", "!", "?")

_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_NUMBER = re.compile(r"\b\d[\d.,]*\b")
_CAPITALIZED_WORD = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]{2,}\b")


def _is_mid_sentence(text: str, offset: int) -> bool:
    prefix = text[:offset].rstrip()
    if not prefix:
        return False
    return prefix[-1] not in _SENTENCE_END


def flag_risky_tokens(text: str) -> list:
    flagged = []

    for match in _ACRONYM.finditer(text):
        flagged.append(_build_flag(text, match, "acronym"))

    for match in _NUMBER.finditer(text):
        flagged.append(_build_flag(text, match, "number"))

    for match in _CAPITALIZED_WORD.finditer(text):
        if _is_mid_sentence(text, match.start()):
            flagged.append(_build_flag(text, match, "foreign_name"))

    flagged.sort(key=lambda f: f["char_offset"])
    return flagged


def _build_flag(text: str, match, reason: str) -> dict:
    offset = match.start()
    start = max(0, offset - CONTEXT_RADIUS)
    end = min(len(text), offset + CONTEXT_RADIUS)
    return {
        "token": match.group(0),
        "reason": reason,
        "char_offset": offset,
        "context": text[start:end],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pronunciation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pronunciation.py tests/test_pronunciation.py
git commit -m "feat: add pronunciation risk flagging"
```

---

## Task 10: Fix `translate.py`

**Files:**
- Modify: `src/translate.py` (whole file rewritten — see below)
- Test: `tests/test_translate.py`

**Interfaces:**
- Produces: `split_into_sentences(texto: str) -> list[str]` (renamed from `dividir_texto_em_frases`); `translate(texto_original: str, source: str, target: str, limite: int = 4000) -> str` (`source`/`target` now required positional/keyword args, no more hardcoded `'auto'`/`'portuguese'`).
- Breaking change: any caller using the old `dividir_texto_em_frases` name or calling `translate(text)` without `source`/`target` must be updated (no callers exist yet in `src/` outside this file).

- [ ] **Step 1: Write the failing test**

Create `tests/test_translate.py`:

```python
import pytest

import src.translate as translate_module
from src.translate import split_into_sentences, translate


class _FakeTranslator:
    def __init__(self, source, target):
        self.source = source
        self.target = target

    def translate(self, text):
        return f"[{self.source}->{self.target}] {text}"


def test_split_into_sentences_splits_on_punctuation():
    result = split_into_sentences("Hello world. How are you? Fine!")

    assert result == ["Hello world.", "How are you?", "Fine!"]


def test_translate_requires_source_and_target():
    with pytest.raises(TypeError):
        translate("Hello world.")


def test_translate_passes_source_and_target_through(monkeypatch):
    monkeypatch.setattr(translate_module, "GoogleTranslator", _FakeTranslator)

    result = translate("Hello world.", source="en", target="pt", limite=4000)

    assert result == "[en->pt] Hello world."


def test_translate_batches_respect_limite(monkeypatch):
    captured_batches = []

    class _RecordingTranslator(_FakeTranslator):
        def translate(self, text):
            captured_batches.append(text)
            return text

    monkeypatch.setattr(translate_module, "GoogleTranslator", _RecordingTranslator)

    long_text = "Sentence one. Sentence two. Sentence three."
    translate(long_text, source="en", target="pt", limite=15)

    assert len(captured_batches) > 1
    assert all(len(batch) <= 15 for batch in captured_batches)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_translate.py -v`
Expected: FAIL (`ImportError: cannot import name 'split_into_sentences'`)

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `src/translate.py`:

```python
import re

from deep_translator import GoogleTranslator
from tqdm import tqdm


def split_into_sentences(texto: str) -> list:
    frases = re.split(r'(?<=[.!?]) +', texto)
    return [frase.strip() for frase in frases if frase.strip()]


def translate(texto_original: str, source: str, target: str, limite: int = 4000) -> str:
    tradutor = GoogleTranslator(source=source, target=target)

    frases = split_into_sentences(texto_original)

    partes = []
    lote_atual = ""

    for frase in frases:
        if len(lote_atual) + len(frase) + 1 <= limite:
            lote_atual = f"{lote_atual} {frase}".strip() if lote_atual else frase
        else:
            partes.append(lote_atual)
            lote_atual = frase

    if lote_atual:
        partes.append(lote_atual)

    partes_traduzidas = [
        tradutor.translate(parte) for parte in tqdm(partes, desc="Traduzindo lotes")
    ]

    return ''.join(partes_traduzidas)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_translate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/translate.py tests/test_translate.py
git commit -m "fix: require explicit source/target in translate(), rename split_into_sentences"
```

---

## Task 11: Fix `text_to_speech.py`

**Files:**
- Modify: `src/text_to_speech.py:21-24`
- Test: `tests/test_text_to_speech.py`

**Interfaces:**
- Produces: `text_to_speech(text, output_file, voice=..., rate=..., pitch=..., volume=..., format=...)` (signature unchanged) — now raises `FileExistsError` instead of silently printing and returning when `output_file` already exists.

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_to_speech.py`:

```python
import asyncio

import pytest

from src.text_to_speech import text_to_speech


def test_text_to_speech_raises_if_output_exists(tmp_path):
    output_file = tmp_path / "existing.mp3"
    output_file.write_bytes(b"already here")

    with pytest.raises(FileExistsError):
        asyncio.run(text_to_speech("Hello world.", str(output_file)))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_text_to_speech.py -v`
Expected: FAIL — no exception raised (current code prints and returns `None`)

- [ ] **Step 3: Fix the implementation**

In `src/text_to_speech.py`, replace lines 21-24:

```python
    # Verifica se o arquivo de saída já existe
    if os.path.exists(output_file):
        print(f"O arquivo {output_file} já existe. Escolha outro nome ou exclua o arquivo existente.")
        return
```

with:

```python
    if os.path.exists(output_file):
        raise FileExistsError(
            f"{output_file} already exists. Delete it before regenerating."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_text_to_speech.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/text_to_speech.py tests/test_text_to_speech.py
git commit -m "fix: raise FileExistsError instead of silently skipping existing output"
```

---

## Task 12: Test coverage for `tools.py` (no production code change)

**Files:**
- Test: `tests/test_tools.py`

`src/tools.py` stays exactly as-is per the plan ("já corretos e pequenos, mantêm-se como estão") — this task only adds the missing test coverage called for in the plan's Verification section.

**Interfaces:**
- Consumes: `dividir_texto_em_partes(texto, n)`, `combinar_arquivos_audio(arquivos, arquivo_saida)` (existing, unchanged).

- [ ] **Step 1: Write the failing test**

Create `tests/test_tools.py`:

```python
from pydub import AudioSegment

from src.tools import combinar_arquivos_audio, dividir_texto_em_partes


def test_dividir_texto_em_partes_does_not_break_words():
    texto = "one two three four five six seven eight nine ten"

    partes = dividir_texto_em_partes(texto, 3)

    assert len(partes) == 3
    rejoined = " ".join(partes)
    for word in texto.split():
        assert word in rejoined.split()


def test_dividir_texto_em_partes_covers_full_text():
    texto = "alpha beta gamma delta epsilon"

    partes = dividir_texto_em_partes(texto, 2)

    assert "".join(partes).replace(" ", "") == texto.replace(" ", "")


def test_combinar_arquivos_audio_concatenates_files(tmp_path):
    file_a = tmp_path / "a.mp3"
    file_b = tmp_path / "b.mp3"
    output = tmp_path / "combined.mp3"

    AudioSegment.silent(duration=500).export(str(file_a), format="mp3")
    AudioSegment.silent(duration=700).export(str(file_b), format="mp3")

    combinar_arquivos_audio([str(file_a), str(file_b)], str(output))

    assert output.exists()
    combined = AudioSegment.from_mp3(str(output))
    assert len(combined) >= 1000  # allow mp3 encoding rounding
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools'` (only fails if `src` isn't on `pythonpath` yet — by this point in the plan it already is from Task 1; if the module truly can't be found, this indicates the scaffolding regressed and must be fixed first)

- [ ] **Step 3: No production code change needed**

`src/tools.py` already implements the behavior under test. If Step 2 failed only due to import resolution, fix `pyproject.toml`/`pythonpath`, not `tools.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tools.py
git commit -m "test: add coverage for existing tools.py functions"
```

---

## Task 13: `pipeline`

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `read_or_extract` (Task 5), `trim_to_boundaries` (Task 6), `extract_title_author` (Task 7), `build_intro_text` (Task 8), `translate` (Task 10), `text_to_speech` (Task 11), `dividir_texto_em_partes`/`combinar_arquivos_audio` (`src/tools.py`, unchanged).
- Produces: `convert_book_to_audio(book_path, start_char, end_char, output_file, voice="pt-BR-AntonioNeural", translate_to=None, translate_source="auto", n_parts=10, format=None) -> str` — returns `output_file` path on success. Raises `FileExistsError` up front if `output_file` already exists (before doing any synthesis work).

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline.py`. Monkeypatches `text_to_speech` (no network/edge-tts call) and `translate` (no network call), and produces real tiny mp3s via `pydub` so `combinar_arquivos_audio` runs for real:

```python
import pytest
from pydub import AudioSegment

import src.pipeline as pipeline_module
from src.pipeline import convert_book_to_audio


async def _fake_text_to_speech(text, output_file, **kwargs):
    AudioSegment.silent(duration=200).export(output_file, format="mp3")


def _fake_translate(texto, source, target, limite=4000):
    return texto.upper()


def test_convert_book_to_audio_produces_output_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "text_to_speech", _fake_text_to_speech)
    monkeypatch.setattr(pipeline_module, "translate_text", _fake_translate)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one. " * 50, encoding="utf-8")
    output_file = tmp_path / "out.mp3"

    monkeypatch.chdir(tmp_path)
    result = convert_book_to_audio(
        book_path=str(book_path.name),
        start_char=0,
        end_char=len(book_path.read_text(encoding="utf-8")),
        output_file=str(output_file),
        n_parts=2,
    )

    assert result == str(output_file)
    assert output_file.exists()


def test_convert_book_to_audio_refuses_existing_output(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "text_to_speech", _fake_text_to_speech)
    monkeypatch.setattr(pipeline_module, "translate_text", _fake_translate)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one.", encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    output_file.write_bytes(b"already here")

    with pytest.raises(FileExistsError):
        convert_book_to_audio(
            book_path=str(book_path),
            start_char=0,
            end_char=len("Chapter one."),
            output_file=str(output_file),
        )


def test_convert_book_to_audio_translates_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "text_to_speech", _fake_text_to_speech)
    captured = {}

    def _spy_translate(texto, source, target, limite=4000):
        captured["source"] = source
        captured["target"] = target
        return texto

    monkeypatch.setattr(pipeline_module, "translate_text", _spy_translate)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one.", encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    monkeypatch.chdir(tmp_path)

    convert_book_to_audio(
        book_path=str(book_path.name),
        start_char=0,
        end_char=len("Chapter one."),
        output_file=str(output_file),
        translate_to="pt",
        n_parts=1,
    )

    assert captured == {"source": "auto", "target": "pt"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.pipeline'`

- [ ] **Step 3: Write minimal implementation**

Create `src/pipeline.py`:

```python
import asyncio
from pathlib import Path
from typing import Optional

from src.boundary import trim_to_boundaries
from src.intro import build_intro_text
from src.metadata import extract_title_author
from src.text_cache import read_or_extract
from src.text_to_speech import text_to_speech
from src.tools import combinar_arquivos_audio, dividir_texto_em_partes
from src.translate import translate as translate_text


def convert_book_to_audio(
    book_path: str,
    start_char: int,
    end_char: int,
    output_file: str,
    voice: str = "pt-BR-AntonioNeural",
    translate_to: Optional[str] = None,
    translate_source: str = "auto",
    n_parts: int = 10,
    format: Optional[str] = None,
) -> str:
    if Path(output_file).exists():
        raise FileExistsError(
            f"{output_file} already exists. Delete it before regenerating."
        )

    text = read_or_extract(book_path, format=format)
    trimmed = trim_to_boundaries(text, start_char, end_char)
    metadata = extract_title_author(book_path, format=format)
    intro_text = build_intro_text(metadata)

    body_text = (
        translate_text(trimmed, translate_source, translate_to)
        if translate_to
        else trimmed
    )

    parts = dividir_texto_em_partes(body_text, n_parts)

    tmp_dir = Path(output_file).parent / ".tmp_audio_parts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    part_files = []

    intro_file = tmp_dir / "000_intro.mp3"
    asyncio.run(text_to_speech(intro_text, str(intro_file), voice=voice))
    part_files.append(str(intro_file))

    for i, part in enumerate(parts, start=1):
        part_file = tmp_dir / f"{i:03d}.mp3"
        asyncio.run(text_to_speech(part, str(part_file), voice=voice))
        part_files.append(str(part_file))

    combinar_arquivos_audio(part_files, output_file)

    for f in part_files:
        Path(f).unlink()
    tmp_dir.rmdir()

    return output_file
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add convert_book_to_audio pipeline orchestrator"
```

---

## Task 14: `cli`

**Files:**
- Create: `src/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `read_or_extract`/`cache_path_for` (Task 5), `find_boundary_candidates` (Task 6), `extract_title_author` (Task 7), `flag_risky_tokens` (Task 9), `convert_book_to_audio` (Task 13).
- Produces: `main(argv=None) -> int` with subcommands `doctor`, `inspect <book_path> [--format] [--json]`, `pronunciation <book_path> --start-char N --end-char M [--json]`, `convert <book_path> --start-char N --end-char M [--voice] [--translate-to] --output out.mp3`. Runnable as `python -m src.cli <subcommand> ...`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
import json

import pytest

import src.cli as cli_module
from src.cli import main


def test_doctor_fails_when_ffmpeg_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: None)

    exit_code = main(["doctor"])

    assert exit_code == 1
    assert "ffmpeg" in capsys.readouterr().out.lower()


def test_doctor_passes_when_everything_present(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    exit_code = main(["doctor"])

    assert exit_code == 0
    assert "[OK]" in capsys.readouterr().out


def test_inspect_json_matches_schema(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text("CHAPTER I\nIt was a dark night.", encoding="utf-8")

    exit_code = main(["inspect", str(book_path), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {
        "book_path", "format", "text_path", "char_count", "metadata",
        "boundary_candidates",
    }
    assert payload["format"] == "txt"
    assert payload["char_count"] == len(book_path.read_text(encoding="utf-8"))
    assert any(c["kind"] == "chapter_heading" for c in payload["boundary_candidates"])


def test_pronunciation_json_offsets_relative_to_book(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    text = "Intro padding. ISBN 1865 here."
    book_path.write_text(text, encoding="utf-8")
    start = text.index("ISBN")

    exit_code = main([
        "pronunciation", str(book_path),
        "--start-char", str(start), "--end-char", str(len(text)), "--json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    isbn_flag = next(f for f in payload["flagged_tokens"] if f["token"] == "ISBN")
    assert isbn_flag["char_offset"] == start


def test_convert_refuses_existing_output(tmp_path, monkeypatch, capsys):
    output = tmp_path / "out.mp3"
    output.write_bytes(b"already here")
    called = {"value": False}

    def _fail_if_called(*args, **kwargs):
        called["value"] = True

    monkeypatch.setattr(cli_module, "convert_book_to_audio", _fail_if_called)

    exit_code = main([
        "convert", str(tmp_path / "book.txt"),
        "--start-char", "0", "--end-char", "10", "--output", str(output),
    ])

    assert exit_code == 1
    assert called["value"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.cli'`

- [ ] **Step 3: Write minimal implementation**

Create `src/cli.py`:

```python
import argparse
import json
import shutil
import sys
from pathlib import Path

from src.boundary import find_boundary_candidates
from src.metadata import extract_title_author
from src.pipeline import convert_book_to_audio
from src.pronunciation import flag_risky_tokens
from src.text_cache import cache_path_for, read_or_extract

_REQUIRED_MODULES = ("edge_tts", "ebooklib", "fitz", "bs4", "deep_translator", "pydub")


def cmd_doctor(args) -> int:
    problems = []
    if shutil.which("ffmpeg") is None:
        problems.append("ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`).")
    for module_name in _REQUIRED_MODULES:
        try:
            __import__(module_name)
        except ImportError:
            problems.append(f"Python package missing: {module_name}. Run `pip install -r requirements.txt`.")

    if problems:
        for problem in problems:
            print(f"[FAIL] {problem}")
        return 1

    print("[OK] All dependencies found.")
    return 0


def cmd_inspect(args) -> int:
    fmt = args.format
    text = read_or_extract(args.book_path, format=fmt)
    metadata = extract_title_author(args.book_path, format=fmt)
    candidates = find_boundary_candidates(text)

    result = {
        "book_path": args.book_path,
        "format": fmt or Path(args.book_path).suffix.lstrip(".").lower(),
        "text_path": str(cache_path_for(args.book_path)),
        "char_count": len(text),
        "metadata": {
            "title": metadata.title,
            "author": metadata.author,
            "subtitle": metadata.subtitle,
        },
        "boundary_candidates": [
            {
                "char_offset": c.char_offset,
                "kind": c.kind,
                "matched_text": c.matched_text,
                "preview": c.preview,
            }
            for c in candidates
        ],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Title: {metadata.title}\nAuthor: {metadata.author}\nChars: {len(text)}")
        for c in candidates:
            print(f"  [{c.kind}] @ {c.char_offset}: {c.matched_text!r}")

    return 0


def cmd_pronunciation(args) -> int:
    text = read_or_extract(args.book_path)
    excerpt = text[args.start_char:args.end_char]
    flagged = flag_risky_tokens(excerpt)
    for flag in flagged:
        flag["char_offset"] += args.start_char

    result = {
        "start_char": args.start_char,
        "end_char": args.end_char,
        "flagged_tokens": flagged,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for flag in flagged:
            print(f"  [{flag['reason']}] {flag['token']!r} @ {flag['char_offset']}")

    return 0


def cmd_convert(args) -> int:
    if Path(args.output).exists():
        print(f"[FAIL] {args.output} already exists.", file=sys.stderr)
        return 1

    convert_book_to_audio(
        book_path=args.book_path,
        start_char=args.start_char,
        end_char=args.end_char,
        output_file=args.output,
        voice=args.voice,
        translate_to=args.translate_to,
    )
    print(f"[OK] Audiobook saved to {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="book-to-audiobook")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor").set_defaults(func=cmd_doctor)

    p_inspect = subparsers.add_parser("inspect")
    p_inspect.add_argument("book_path")
    p_inspect.add_argument("--format", default=None)
    p_inspect.add_argument("--json", action="store_true")
    p_inspect.set_defaults(func=cmd_inspect)

    p_pronunciation = subparsers.add_parser("pronunciation")
    p_pronunciation.add_argument("book_path")
    p_pronunciation.add_argument("--start-char", type=int, required=True)
    p_pronunciation.add_argument("--end-char", type=int, required=True)
    p_pronunciation.add_argument("--json", action="store_true")
    p_pronunciation.set_defaults(func=cmd_pronunciation)

    p_convert = subparsers.add_parser("convert")
    p_convert.add_argument("book_path")
    p_convert.add_argument("--start-char", type=int, required=True)
    p_convert.add_argument("--end-char", type=int, required=True)
    p_convert.add_argument("--voice", default="pt-BR-AntonioNeural")
    p_convert.add_argument("--translate-to", default=None)
    p_convert.add_argument("--output", required=True)
    p_convert.set_defaults(func=cmd_convert)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Manual smoke check**

Run: `python -m src.cli doctor`
Expected: prints `[OK] All dependencies found.` (or clearly lists what's missing) with exit code 0 or 1 accordingly.

- [ ] **Step 6: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat: add cli with doctor, inspect, pronunciation, convert subcommands"
```

---

## Task 15: `SKILL.md`

**Files:**
- Create: `.claude/skills/book-to-audiobook/SKILL.md`

**Interfaces:**
- Consumes: `python -m src.cli doctor|inspect|pronunciation|convert` (Task 14) as the only way this skill touches code (per `docs/modernization-plan.md`: "skills são documentação de processo testada por pressão, não replicam lógica determinística").

This task has no `pytest` coverage — `SKILL.md` is process documentation, not code. Acceptance is a scripted content check plus the manual RED-GREEN-REFACTOR skill-pressure-test described in `docs/modernization-plan.md`'s Prompt 11 (out of scope to run automatically here; documented as the acceptance step).

- [ ] **Step 1: Write the acceptance check first**

Create `/tmp/check_skill_md.sh` (not committed — a throwaway verification script):

```bash
#!/usr/bin/env bash
set -euo pipefail
FILE=".claude/skills/book-to-audiobook/SKILL.md"

grep -q "^description:" "$FILE" || { echo "FAIL: missing frontmatter description"; exit 1; }
for gate in "Setup" "preferences" "Inspe" "aprova" "confirma" "revisa" "Convert" "confere"; do
  grep -qi "$gate" "$FILE" || { echo "FAIL: missing gate mention: $gate"; exit 1; }
done
grep -qi "common mistakes\|erros comuns" "$FILE" || { echo "FAIL: missing common mistakes section"; exit 1; }
echo "PASS"
```

Run: `bash /tmp/check_skill_md.sh`
Expected: FAIL (`.claude/skills/book-to-audiobook/SKILL.md` does not exist yet)

- [ ] **Step 2: Write `SKILL.md`**

Create `.claude/skills/book-to-audiobook/SKILL.md`:

```markdown
---
name: book-to-audiobook
description: Convert an epub/pdf/txt book into a narrated pt-BR (or original-language) audiobook. Use when the user asks to "turn this book into an audiobook", "narrate this epub", or similar — for any book conversion request in this repository.
---

# Book to Audiobook

Converts a book file into an MP3 audiobook using free, keyless services
(`edge-tts` for speech, `deep-translator`'s `GoogleTranslator` for optional
translation — both need internet, neither needs an API key).

All operational choices (voice, target language, input file, output path)
are asked in this conversation, every time. Never read from `.env` — there
is nothing to configure there.

This skill is a thin conversational wrapper around `python -m src.cli`. All
actual text extraction, boundary detection, and audio synthesis is
deterministic code in `src/` — don't reimplement it, call the CLI via Bash.

## Gates

Work through these in order. Each gate ends with an explicit stop-and-wait
for the user — do not skip ahead, even if a step "looks obvious" (this
applies especially to Gate 3 and Gate 5, see Common Mistakes below).

### Gate 0 — Setup

Run `python -m src.cli doctor`. If it reports missing dependencies, install
them (`pip install -r requirements.txt`) or tell the user to install
`ffmpeg` (`brew install ffmpeg` / `apt install ffmpeg`). First run can be
slow while dependencies install — say so, so it doesn't read as a hang.

### Gate 1 — Book and preferences

Ask the user for:
- The book's name (not full path — look for it inside `books/private/`).
- Target language, or "no translation".
- Voice (offer the default `pt-BR-AntonioNeural` if they have no preference).

### Gate 2 — Inspect

Run `python -m src.cli inspect <path> --json`. Parse the JSON: metadata
(title/author/subtitle) and `boundary_candidates`.

### Gate 3 — Confirm the start/end cut

Show the user each boundary candidate's `preview` and `kind`. **Wait for
explicit confirmation of `--start-char`/`--end-char` before proceeding.**
This is the core value of the skill — the semantic judgment of where real
content starts/ends (table of contents, dedication, preface at the start;
afterword, ads for other books at the end) that today only a human makes.
Gutenberg markers, when present, are one heuristic among five — not an
automatic answer.

### Gate 4 — Confirm title/author/subtitle

Show the metadata from Gate 2's JSON. Let the user correct it. This feeds
the spoken intro (e.g. "Alice's Adventures in Wonderland. De Lewis
Carroll.").

### Gate 5 — Review pronunciation

Run `python -m src.cli pronunciation <path> --start-char N --end-char M --json`
(using the offsets confirmed in Gate 3). Show the user the flagged tokens
(acronyms, numbers, foreign names) with context. Let them correct spellings
that the TTS voice would mispronounce. This is a **text** review, not a
phonetic dictionary — same pattern as `pitch-video-studio`.

### Gate 6 — Convert

Only after Gates 1-5 are confirmed:

```
python -m src.cli convert <path> \
  --start-char <N> --end-char <M> \
  --voice <voice> [--translate-to <lang>] \
  --output <output.mp3>
```

### Gate 7 — Review the result

Report the output file's size/duration to the user. Ask them to listen and
confirm it sounds right.

## Common Mistakes

- Treating the table of contents or a Gutenberg marker as automatically
  "the start" without showing the preview to the user (skips Gate 3).
- Jumping straight to `convert` without having shown boundary candidates or
  pronunciation flags — always show Gate 3 and Gate 5 output first.
- Reading voice/language/paths from `.env` — there is no operational config
  file; always ask in the conversation.
- Confusing a preface/dedication (`front_matter`) with the table of
  contents (`table_of_contents`) — they need different treatment; read the
  `preview` field, don't guess from `kind` alone.
```

- [ ] **Step 3: Run the acceptance check**

Run: `bash /tmp/check_skill_md.sh`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/book-to-audiobook/SKILL.md
git commit -m "docs: add book-to-audiobook Claude Code Skill"
```

---

## Task 16: `plugin.json`

**Files:**
- Create: `.claude/skills/book-to-audiobook/.claude-plugin/plugin.json`

**Interfaces:**
- None — static manifest, no code consumes it directly (Claude Code's plugin loader reads it by convention: any `.claude-plugin/plugin.json` inside a skills directory auto-loads as a plugin).

- [ ] **Step 1: Write the acceptance check first**

Run: `python3 -c "import json,sys; d=json.load(open('.claude/skills/book-to-audiobook/.claude-plugin/plugin.json')); sys.exit(0 if 'name' in d else 1)"`
Expected: FAIL (file does not exist yet)

- [ ] **Step 2: Write `plugin.json`**

Create `.claude/skills/book-to-audiobook/.claude-plugin/plugin.json`:

```json
{
  "name": "book-to-audiobook",
  "displayName": "Book to Audiobook",
  "description": "Converte epub/pdf em audiobook narrado (opcionalmente traduzido pra pt-BR), 100% gratuito e sem chave de API (edge-tts e GoogleTranslator são serviços gratuitos, mas online — precisa de internet).",
  "version": "0.1.0",
  "license": "MIT",
  "repository": "https://github.com/gomesfellipe/book-to-audiobook"
}
```

- [ ] **Step 3: Run the acceptance check**

Run: `python3 -c "import json,sys; d=json.load(open('.claude/skills/book-to-audiobook/.claude-plugin/plugin.json')); sys.exit(0 if 'name' in d else 1)"`
Expected: exit code 0, no output (PASS)

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/book-to-audiobook/.claude-plugin/plugin.json
git commit -m "chore: package book-to-audiobook skill as a plugin"
```

---

## Final Verification

- [ ] Run the full suite: `pytest -v`
  Expected: all tests across `tests/loaders/`, `tests/test_text_cache.py`, `tests/test_boundary.py`, `tests/test_metadata.py`, `tests/test_intro.py`, `tests/test_pronunciation.py`, `tests/test_translate.py`, `tests/test_text_to_speech.py`, `tests/test_tools.py`, `tests/test_pipeline.py`, `tests/test_cli.py` pass.
- [ ] `grep -rn "os.getenv\|load_dotenv" src/` returns nothing (no module reads operational config from `.env`).
- [ ] `grep -n "PyPDF2" requirements.txt` returns nothing.
- [ ] `python -m src.cli doctor` runs without crashing.
- [ ] No file under `tests/` contains real commercial book text — only synthetic fixtures built in-test or short literal strings.