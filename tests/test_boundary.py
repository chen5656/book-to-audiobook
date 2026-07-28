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