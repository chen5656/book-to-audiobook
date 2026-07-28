import asyncio

import pytest

from src.text_to_speech import text_to_speech


def test_text_to_speech_raises_if_output_exists(tmp_path):
    output_file = tmp_path / "existing.mp3"
    output_file.write_bytes(b"already here")

    with pytest.raises(FileExistsError):
        asyncio.run(text_to_speech("Hello world.", str(output_file)))