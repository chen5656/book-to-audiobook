import pytest
from pydub import AudioSegment

import src.pipeline as pipeline_module
from src.pipeline import convert_book_to_audio


async def _fake_text_to_speech(text, output_file, **kwargs):
    AudioSegment.silent(duration=200).export(output_file, format="mp3")


def _fake_translate(texto, source, target, limite=4000):
    return texto.upper()


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
        n_parts=2,
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
        )


def test_convert_book_to_audio_translates_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "text_to_speech", _fake_text_to_speech)
    captured = {}

    def _spy_translate(texto, source, target, limite=4000):
        captured["source"] = source
        captured["target"] = target
        return texto

    monkeypatch.setattr(pipeline_module, "translate_text", _spy_translate)

    book_path = tmp_path / "book.txt"
    book_path.write_text("Chapter one.", encoding="utf-8")
    output_file = tmp_path / "out.mp3"
    monkeypatch.chdir(tmp_path)

    convert_book_to_audio(
        book_path=str(book_path.name),
        start_char=0,
        end_char=len("Chapter one."),
        output_file=str(output_file),
        translate_to="pt",
        n_parts=1,
    )

    assert captured == {"source": "auto", "target": "pt"}


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
            n_parts=2,
        )

    leftover = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp_audio_parts")]
    assert leftover == []