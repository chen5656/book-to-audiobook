import json

import pytest

import src.cli as cli_module
from src.cli import main


def test_doctor_fails_when_ffmpeg_missing(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: None)

    exit_code = main(["doctor"])

    assert exit_code == 1
    assert "ffmpeg" in capsys.readouterr().out.lower()


def test_doctor_checks_tqdm(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    assert "tqdm" in cli_module._REQUIRED_MODULES


def test_doctor_passes_when_everything_present(monkeypatch, capsys):
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    exit_code = main(["doctor"])

    assert exit_code == 0
    assert "[OK]" in capsys.readouterr().out


def test_inspect_json_matches_schema(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text("CHAPTER I\nIt was a dark night.", encoding="utf-8")

    exit_code = main(["inspect", str(book_path), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {
        "book_path", "format", "text_path", "char_count", "metadata",
        "boundary_candidates", "cleaning",
    }
    assert payload["format"] == "txt"
    assert payload["char_count"] == len(book_path.read_text(encoding="utf-8"))
    assert any(c["kind"] == "chapter_heading" for c in payload["boundary_candidates"])
    assert payload["cleaning"] == {
        "decorative_lines_removed": 0, "roman_chapters_converted": 1,
    }


def test_inspect_json_reports_cleaning_stats(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text(
        "CHAPTER IV.The Rabbit\n*      *      *      *      *      *      *\nMore.\n",
        encoding="utf-8",
    )

    exit_code = main(["inspect", str(book_path), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cleaning"] == {
        "decorative_lines_removed": 1, "roman_chapters_converted": 1,
    }


def test_pronunciation_json_offsets_relative_to_book(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    text = "Intro padding. ISBN 1865 here."
    book_path.write_text(text, encoding="utf-8")
    start = text.index("ISBN")

    exit_code = main([
        "pronunciation", str(book_path),
        "--start-char", str(start), "--end-char", str(len(text)), "--json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    isbn_flag = next(f for f in payload["flagged_tokens"] if f["token"] == "ISBN")
    assert isbn_flag["char_offset"] == start


def test_pronunciation_rejects_invalid_bounds(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text("Intro padding. ISBN 1865 here.", encoding="utf-8")

    exit_code = main([
        "pronunciation", str(book_path),
        "--start-char", "999", "--end-char", "5", "--json",
    ])

    assert exit_code == 1


def test_pronunciation_flags_translated_text_when_requested(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text("Intro padding. Hello world here.", encoding="utf-8")

    def _fake_read_or_translate(book_path_, start, end, source, target, trimmed_text):
        return "ISBN 1865 translated here."

    monkeypatch.setattr(cli_module, "read_or_translate", _fake_read_or_translate)

    exit_code = main([
        "pronunciation", str(book_path),
        "--start-char", "0", "--end-char", str(len(book_path.read_text(encoding="utf-8"))),
        "--source-lang", "en", "--translate-to", "pt", "--json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["translated_to"] == "pt"
    isbn_flag = next(f for f in payload["flagged_tokens"] if f["token"] == "ISBN")
    assert isbn_flag["char_offset"] == 0


def test_pronunciation_requires_source_lang_when_translating(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    book_path = tmp_path / "book.txt"
    book_path.write_text("Intro padding. Hello world here.", encoding="utf-8")

    exit_code = main([
        "pronunciation", str(book_path),
        "--start-char", "0", "--end-char", str(len(book_path.read_text(encoding="utf-8"))),
        "--translate-to", "pt", "--json",
    ])

    assert exit_code == 1


def test_convert_refuses_existing_output(tmp_path, monkeypatch, capsys):
    output = tmp_path / "out.mp3"
    output.write_bytes(b"already here")
    called = {"value": False}

    def _fail_if_called(*args, **kwargs):
        called["value"] = True

    monkeypatch.setattr(cli_module, "convert_book_to_audio", _fail_if_called)

    exit_code = main([
        "convert", str(tmp_path / "book.txt"),
        "--start-char", "0", "--end-char", "10", "--output", str(output),
        "--voice", "en-US-GuyNeural", "--source-lang", "en",
    ])

    assert exit_code == 1
    assert called["value"] is False


def test_voices_lists_filtered_results(monkeypatch, capsys):
    async def _fake_list_voices(locale_prefix=None):
        all_voices = [
            {"ShortName": "en-US-GuyNeural", "Gender": "Male", "Locale": "en-US"},
            {"ShortName": "pt-BR-AntonioNeural", "Gender": "Male", "Locale": "pt-BR"},
        ]
        if not locale_prefix:
            return all_voices
        return [v for v in all_voices if v["Locale"].lower().startswith(locale_prefix.lower())]

    monkeypatch.setattr(cli_module, "list_voices", _fake_list_voices)

    exit_code = main(["voices", "--lang", "pt", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == [{"ShortName": "pt-BR-AntonioNeural", "Gender": "Male", "Locale": "pt-BR"}]