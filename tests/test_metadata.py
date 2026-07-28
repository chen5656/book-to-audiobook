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


def test_extract_title_author_from_txt_uses_first_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "book.txt"
    path.write_text("My Book Title\n\nOnce upon a time...", encoding="utf-8")

    result = extract_title_author(str(path))

    assert result.title == "My Book Title"
    assert result.author is None


def test_extract_title_author_from_txt_uses_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "book.txt"
    path.write_text("Original Title\n\nOnce upon a time...", encoding="utf-8")

    first = extract_title_author(str(path.name))
    assert first.title == "Original Title"

    path.write_text("Changed Title\n\nDifferent story...", encoding="utf-8")
    second = extract_title_author(str(path.name))

    assert second.title == "Original Title"