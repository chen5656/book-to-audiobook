from src.loaders.txt_loader import load_txt


def test_load_txt_returns_file_contents(tmp_path):
    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter 1\n\nHello world.", encoding="utf-8")

    result = load_txt(str(book_path))

    assert result == "Chapter 1\n\nHello world."