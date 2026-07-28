import pytest
from pydub import AudioSegment

import src.pipeline as pipeline_module
import src.text_cache as text_cache_module
from src.pipeline import convert_book_to_audio


async def _fake_text_to_speech(text, output_file, **kwargs):
    AudioSegment.silent(duration=200).export(output_file, format="mp3")


def _fake_translate(text, source, target, limit=4000):
    return text.upper()


def test_convert_book_to_audio_produces_output_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "text_to_speech", _fake_text_to_speech)
    monkeypatch.setattr(pipeline_module, "translate_text", _fake_translate)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one. " * 50, encoding="utf-8")
    output_file = tmp_path / "out.mp3"

    monkeypatch.chdir(tmp_path)
    result = convert_book_to_audio(
        book_path=str(book_path.name),
        start_char=0,
        end_char=len(book_path.read_text(encoding="utf-8")),
        output_file=str(output_file),
        voice="en-US-GuyNeural",
        translate_source="en",
    )

    assert result == str(output_file)
    assert output_file.exists()


def test_convert_book_to_audio_refuses_existing_output(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "text_to_speech", _fake_text_to_speech)
    monkeypatch.setattr(pipeline_module, "translate_text", _fake_translate)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one.", encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    output_file.write_bytes(b"already here")

    with pytest.raises(FileExistsError):
        convert_book_to_audio(
            book_path=str(book_path),
            start_char=0,
            end_char=len("Chapter one."),
            output_file=str(output_file),
            voice="en-US-GuyNeural",
            translate_source="en",
        )


def test_convert_book_to_audio_translates_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "text_to_speech", _fake_text_to_speech)
    captured = []

    def _spy_translate(text, source, target, limit=4000):
        captured.append({"source": source, "target": target})
        return text

    monkeypatch.setattr(pipeline_module, "translate_text", _spy_translate)
    monkeypatch.setattr(text_cache_module, "translate_text", _spy_translate)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one.", encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    monkeypatch.chdir(tmp_path)

    convert_book_to_audio(
        book_path=str(book_path.name),
        start_char=0,
        end_char=len("Chapter one."),
        output_file=str(output_file),
        voice="en-US-GuyNeural",
        translate_source="en",
        translate_to="pt",
    )

    assert {"source": "en", "target": "pt"} in captured


def test_convert_book_to_audio_cleans_up_temp_files_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "translate_text", _fake_translate)

    async def _failing_text_to_speech(text, output_file, **kwargs):
        raise RuntimeError("simulated transient TTS failure")

    monkeypatch.setattr(pipeline_module, "text_to_speech", _failing_text_to_speech)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one. " * 50, encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError):
        convert_book_to_audio(
            book_path=str(book_path.name),
            start_char=0,
            end_char=len(book_path.read_text(encoding="utf-8")),
            output_file=str(output_file),
            voice="en-US-GuyNeural",
            translate_source="en",
        )

    leftover = list((tmp_path / ".cache").glob(".tmp_audio_parts_*"))
    assert leftover == []


def test_convert_book_to_audio_escalates_chunk_count_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "translate_text", _fake_translate)
    calls = {"count": 0}

    async def _flaky_text_to_speech(text, output_file, **kwargs):
        if "intro" in output_file:
            AudioSegment.silent(duration=200).export(output_file, format="mp3")
            return
        calls["count"] += 1
        if calls["count"] <= 2:
            raise RuntimeError("simulated transient TTS failure")
        AudioSegment.silent(duration=200).export(output_file, format="mp3")

    monkeypatch.setattr(pipeline_module, "text_to_speech", _flaky_text_to_speech)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one. " * 50, encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    monkeypatch.chdir(tmp_path)

    result = convert_book_to_audio(
        book_path=str(book_path.name),
        start_char=0,
        end_char=len(book_path.read_text(encoding="utf-8")),
        output_file=str(output_file),
        voice="en-US-GuyNeural",
        translate_source="en",
    )

    assert result == str(output_file)
    assert output_file.exists()
    # 1 (n=1, fails) + 1 (n=2, fails on its first part) + 3 (n=3, all succeed)
    assert calls["count"] == 5


def test_convert_book_to_audio_warns_when_output_seems_truncated(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pipeline_module, "translate_text", _fake_translate)

    async def _short_text_to_speech(text, output_file, **kwargs):
        AudioSegment.silent(duration=50).export(output_file, format="mp3")

    monkeypatch.setattr(pipeline_module, "text_to_speech", _short_text_to_speech)

    book_path = tmp_path / "book.txt"
    book_path.write_text("word " * 2000, encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    monkeypatch.chdir(tmp_path)

    convert_book_to_audio(
        book_path=str(book_path.name),
        start_char=0,
        end_char=len(book_path.read_text(encoding="utf-8")),
        output_file=str(output_file),
        voice="en-US-GuyNeural",
        translate_source="en",
    )

    captured = capsys.readouterr()
    assert "[WARN]" in captured.out
    assert "truncated" in captured.out.lower()
