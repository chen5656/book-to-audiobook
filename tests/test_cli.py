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
        "boundary_candidates",
    }
    assert payload["format"] == "txt"
    assert payload["char_count"] == len(book_path.read_text(encoding="utf-8"))
    assert any(c["kind"] == "chapter_heading" for c in payload["boundary_candidates"])


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
    ])

    assert exit_code == 1
    assert called["value"] is False