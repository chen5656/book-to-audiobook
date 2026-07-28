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
        "Lewis Carroll."
    )


def test_build_intro_text_with_only_title():
    metadata = BookMetadata(title="Alice's Adventures in Wonderland", author=None, subtitle=None)

    result = build_intro_text(metadata)

    assert result == "Alice's Adventures in Wonderland."


def test_build_intro_text_falls_back_when_title_missing():
    metadata = BookMetadata(title=None, author=None, subtitle=None)

    result = build_intro_text(metadata)

    assert result == "Audiobook."