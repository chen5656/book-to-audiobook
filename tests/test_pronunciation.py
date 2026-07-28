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


def test_flag_risky_tokens_deduplicates_repeated_tokens():
    text = "The cat saw Alice. The dog saw Alice too."

    flagged = flag_risky_tokens(text)

    alice_flags = [f for f in flagged if f["token"] == "Alice"]
    assert len(alice_flags) == 1
    assert alice_flags[0]["count"] == 2