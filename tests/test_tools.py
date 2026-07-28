from pydub import AudioSegment

from src.tools import combine_audio_files, split_text_into_parts


def test_split_text_into_parts_does_not_break_words():
    text = "one two three four five six seven eight nine ten"

    parts = split_text_into_parts(text, 3)

    assert len(parts) == 3
    rejoined = " ".join(parts)
    for word in text.split():
        assert word in rejoined.split()


def test_split_text_into_parts_covers_full_text():
    text = "alpha beta gamma delta epsilon"

    parts = split_text_into_parts(text, 2)

    assert "".join(parts).replace(" ", "") == text.replace(" ", "")


def test_combine_audio_files_concatenates_files(tmp_path):
    file_a = tmp_path / "a.mp3"
    file_b = tmp_path / "b.mp3"
    output = tmp_path / "combined.mp3"

    AudioSegment.silent(duration=500).export(str(file_a), format="mp3")
    AudioSegment.silent(duration=700).export(str(file_b), format="mp3")

    combine_audio_files([str(file_a), str(file_b)], str(output))

    assert output.exists()
    combined = AudioSegment.from_mp3(str(output))
    assert len(combined) >= 1000
