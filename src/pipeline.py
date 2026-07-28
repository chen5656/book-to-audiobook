import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from src.boundary import trim_to_boundaries
from src.intro import build_intro_text
from src.metadata import extract_title_author
from src.text_cache import read_or_extract
from src.text_to_speech import text_to_speech
from src.tools import combinar_arquivos_audio, dividir_texto_em_partes
from src.translate import translate as translate_text


def convert_book_to_audio(
    book_path: str,
    start_char: int,
    end_char: int,
    output_file: str,
    voice: str = "pt-BR-AntonioNeural",
    translate_to: Optional[str] = None,
    translate_source: str = "auto",
    n_parts: int = 10,
    format: Optional[str] = None,
) -> str:
    if Path(output_file).exists():
        raise FileExistsError(
            f"{output_file} already exists. Delete it before regenerating."
        )

    text = read_or_extract(book_path, format=format)
    trimmed = trim_to_boundaries(text, start_char, end_char)
    metadata = extract_title_author(book_path, format=format)
    intro_text = build_intro_text(metadata)

    body_text = (
        translate_text(trimmed, translate_source, translate_to)
        if translate_to
        else trimmed
    )

    parts = dividir_texto_em_partes(body_text, n_parts)

    output_parent = Path(output_file).parent
    output_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=".tmp_audio_parts_", dir=str(output_parent)))

    try:
        part_files = []

        intro_file = tmp_dir / "000_intro.mp3"
        asyncio.run(text_to_speech(intro_text, str(intro_file), voice=voice))
        part_files.append(str(intro_file))

        for i, part in enumerate(parts, start=1):
            part_file = tmp_dir / f"{i:03d}.mp3"
            asyncio.run(text_to_speech(part, str(part_file), voice=voice))
            part_files.append(str(part_file))

        combinar_arquivos_audio(part_files, output_file)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return output_file