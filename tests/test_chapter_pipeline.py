import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.chapter_loader import Chapter
from src.chapter_pipeline import batch_convert_chapters, format_chapter_filename, load_progress, save_progress


def test_format_chapter_filename():
    assert format_chapter_filename(1, 4) == "0001.mp3"
    assert format_chapter_filename(42, 4) == "0042.mp3"
    assert format_chapter_filename(100, 3) == "100.mp3"


def test_load_save_progress():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        data = {"completed_chapters": [1, 2, 3]}
        save_progress(tmp_path, data)

        loaded = load_progress(tmp_path)
        assert loaded["completed_chapters"] == [1, 2, 3]
        assert "updated_at" in loaded


@patch("src.chapter_pipeline.convert_single_chapter")
def test_batch_convert_chapters(mock_convert):
    # Setup dummy fake audio creation in mock
    def fake_convert(ch, target_path, voice, rate):
        target_path.write_bytes(b"fake audio data")

    mock_convert.side_effect = fake_convert

    txt_content = "第1章 第一\n内容一\n第2章 第二\n内容二\n第3章 第三\n内容三"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(txt_content)
        txt_path = f.name

    with tempfile.TemporaryDirectory() as out_dir:
        try:
            files = batch_convert_chapters(
                book_path=txt_path,
                output_dir=out_dir,
                start_chapter=1,
                chapter_count=2,
                voice="zh-CN-YunjianNeural",
            )
            assert len(files) == 2
            assert Path(files[0]).name == "0001.mp3"
            assert Path(files[1]).name == "0002.mp3"

            progress_file = Path(out_dir) / "progress.json"
            assert progress_file.exists()
            with open(progress_file, "r", encoding="utf-8") as pf:
                pdata = json.load(pf)
                assert pdata["completed_chapters"] == [1, 2]

            # Re-running batch_convert should skip existing chapters
            mock_convert.reset_mock()
            files_rerun = batch_convert_chapters(
                book_path=txt_path,
                output_dir=out_dir,
                start_chapter=1,
                chapter_count=2,
            )
            assert len(files_rerun) == 2
            assert mock_convert.call_count == 0  # skipped all!
        finally:
            Path(txt_path).unlink(missing_ok=True)
