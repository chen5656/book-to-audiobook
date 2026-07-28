from pathlib import Path

from ebooklib import epub

from src.loaders.epub_loader import load_epub

BOOKS_DIR = Path(__file__).parent.parent.parent / "books"


def _build_synthetic_epub(tmp_path):
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

    path = tmp_path / "synthetic.epub"
    epub.write_epub(str(path), book)
    return str(path)


def test_load_epub_extracts_real_book_content():
    result = load_epub(str(BOOKS_DIR / "alice.epub"))

    assert "CHAPTER I" in result
    assert "Rabbit-Hole" in result
    assert len(result) > 100_000


def test_load_epub_strips_linked_spans(tmp_path):
    path = _build_synthetic_epub(tmp_path)

    result = load_epub(path)

    assert "Hello world." in result
    assert "note 1" not in result


def test_load_epub_collapses_blank_line_runs(tmp_path):
    path = _build_synthetic_epub(tmp_path)

    result = load_epub(path)

    assert "\n\n\n" not in result


def _build_hard_wrapped_epub(tmp_path):
    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Test Author")

    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap1.xhtml", lang="en")
    chapter.content = (
        "<html><body>"
        "<h2>CHAPTER 1.<br/>\nA Title</h2>"
        "<p>\nThis line is hard-wrapped in the source and\n"
        "continues here with no real break.\n</p>"
        '<p class="poem">First verse line,<br/>\nSecond verse line.</p>'
        "<pre>   Right foot,\n     near the Fender,</pre>"
        "</body></html>"
    )
    book.add_item(chapter)
    book.toc = (epub.Link("chap1.xhtml", "Chapter 1", "chap1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    path = tmp_path / "hard_wrapped.epub"
    epub.write_epub(str(path), book)
    return str(path)


def test_load_epub_unwraps_hard_wrapped_paragraph_lines(tmp_path):
    path = _build_hard_wrapped_epub(tmp_path)

    result = load_epub(path)

    assert "and\ncontinues" not in result
    assert "and continues here with no real break." in result


def test_load_epub_preserves_intentional_br_line_breaks(tmp_path):
    path = _build_hard_wrapped_epub(tmp_path)

    result = load_epub(path)

    assert "CHAPTER 1.\nA Title" in result
    assert "First verse line,\nSecond verse line." in result


def test_load_epub_preserves_pre_formatting(tmp_path):
    path = _build_hard_wrapped_epub(tmp_path)

    result = load_epub(path)

    assert "Right foot,\n     near the Fender," in result