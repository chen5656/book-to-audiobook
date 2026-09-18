import tempfile
from pathlib import Path
from src.copier import copy_audio_files_to_device, find_external_drives, natural_sort_key


def test_natural_sort_key():
    filenames = ["10.mp3", "1.mp3", "2.mp3", "100.mp3"]
    sorted_files = sorted(filenames, key=natural_sort_key)
    assert sorted_files == ["1.mp3", "2.mp3", "10.mp3", "100.mp3"]


def test_find_external_drives():
    drives = find_external_drives()
    assert isinstance(drives, list)


def test_copy_audio_files_to_device():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as tgt_dir:
        src_path = Path(src_dir)
        (src_path / "10.mp3").write_text("audio 10")
        (src_path / "1.mp3").write_text("audio 1")
        (src_path / "2.mp3").write_text("audio 2")

        copied = copy_audio_files_to_device(src_dir, tgt_dir)
        assert len(copied) == 3

        tgt_files = [Path(p).name for p in copied]
        assert tgt_files == ["1.mp3", "2.mp3", "10.mp3"]

        assert (Path(tgt_dir) / "1.mp3").read_text() == "audio 1"
        assert (Path(tgt_dir) / "2.mp3").read_text() == "audio 2"
        assert (Path(tgt_dir) / "10.mp3").read_text() == "audio 10"
