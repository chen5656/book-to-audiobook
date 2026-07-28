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