from pathlib import Path

from src.text_cache import cache_path_for, read_or_extract, read_or_extract_raw


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


def test_read_or_extract_raw_returns_uncleaned_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text(
        "CHAPTER IV.The Rabbit\n*      *      *      *      *      *      *\nMore.\n",
        encoding="utf-8",
    )

    result = read_or_extract_raw(str(book_path))

    assert "CHAPTER IV." in result
    assert "*      *" in result
    assert cache_path_for(str(book_path)).exists()


def test_read_or_extract_cleans_freshly_extracted_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text(
        "CHAPTER IV.The Rabbit\n*      *      *      *      *      *      *\nMore.\n",
        encoding="utf-8",
    )

    result = read_or_extract(str(book_path))

    assert "CHAPTER 4." in result
    assert "*      *" not in result


def test_read_or_extract_cleans_a_preexisting_dirty_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text("irrelevant, cache already exists", encoding="utf-8")
    dirty_cache = cache_path_for(str(book_path))
    dirty_cache.parent.mkdir(parents=True, exist_ok=True)
    dirty_cache.write_text(
        "CHAPTER IV.The Rabbit\n*      *      *      *      *      *      *\nMore.\n",
        encoding="utf-8",
    )

    result = read_or_extract(str(book_path))

    assert "CHAPTER 4." in result
    assert "*      *" not in result