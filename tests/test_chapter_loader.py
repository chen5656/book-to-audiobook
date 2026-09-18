import tempfile
from pathlib import Path
from src.chapter_loader import Chapter, load_chapters, load_epub_chapters, load_txt_chapters


def test_load_txt_chapters():
    content = (
        "第1章 初始之章\n"
        "这是第一章的内容。\n\n"
        "第2章 冒险开始\n"
        "这是第二章的内容。"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(content)
        temp_path = f.name

    try:
        chapters = load_chapters(temp_path)
        assert len(chapters) == 2
        assert chapters[0].index == 1
        assert "第1章" in chapters[0].title
        assert "第一章" in chapters[0].text
        assert chapters[1].index == 2
        assert "第2章" in chapters[1].title
        assert "第二章" in chapters[1].text
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_load_epub_chapters_with_alice():
    alice_path = "books/alice.epub"
    if Path(alice_path).exists():
        chapters = load_epub_chapters(alice_path)
        assert len(chapters) > 0
        assert isinstance(chapters[0], Chapter)
        assert chapters[0].index == 1
        assert len(chapters[0].text) > 0
