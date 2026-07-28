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

    book_path.write_text("changed content", encoding="utf-8")
    second = read_or_extract(str(book_path))

    assert second == "original content"