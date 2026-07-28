import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from src.boundary import trim_to_boundaries
from src.intro import build_intro_text
from src.metadata import extract_title_author
from src.text_cache import CACHE_DIR, read_or_extract, read_or_translate
from src.text_to_speech import text_to_speech
from src.tools import combine_audio_files, split_text_into_parts
from src.translate import translate as translate_text

MAX_CHUNKS = 10  # ponytail: linear escalation ceiling; raise if a book still fails at 10 parts
WORDS_PER_MINUTE = 150
# ponytail: naive word-count/150wpm ceiling, tighten the threshold if it false-positives
TRUNCATION_WARNING_RATIO = 0.7


def _estimated_seconds(text: str) -> float:
    return (len(text.split()) / WORDS_PER_MINUTE) * 60


def _synthesize_in_parts(text: str, n: int, tmp_dir: Path, voice: str, rate: str) -> list:
    parts = split_text_into_parts(text, n)
    part_files = []
    start_time = time.time()

    for i, part in enumerate(parts, start=1):
        print(f"Synthesizing part {i}/{n}...", flush=True)
        part_file = tmp_dir / f"{i:03d}.mp3"
        asyncio.run(text_to_speech(part, str(part_file), voice=voice, rate=rate))
        part_files.append(str(part_file))

        elapsed = time.time() - start_time
        avg_per_part = elapsed / i
        eta = avg_per_part * (n - i)
        print(f"  done in {elapsed:.1f}s elapsed, ETA {eta:.1f}s remaining", flush=True)

    return part_files


def convert_book_to_audio(
    book_path: str,
    start_char: int,
    end_char: int,
    output_file: str,
    voice: str,
    translate_source: str,
    rate: str = "+0%",
    translate_to: Optional[str] = None,
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

    if translate_to:
        body_text = read_or_translate(
            book_path, start_char, end_char, translate_source, translate_to, trimmed
        )
        intro_text = translate_text(intro_text, translate_source, translate_to)
    else:
        body_text = trimmed

    output_parent = Path(output_file).parent
    output_parent.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=".tmp_audio_parts_", dir=str(CACHE_DIR)))

    try:
        print("Synthesizing intro...", flush=True)
        intro_file = tmp_dir / "000_intro.mp3"
        asyncio.run(text_to_speech(intro_text, str(intro_file), voice=voice, rate=rate))

        body_files = None
        last_error = None
        for n in range(1, MAX_CHUNKS + 1):
            try:
                body_files = _synthesize_in_parts(body_text, n, tmp_dir, voice, rate)
                break
            except Exception as exc:
                last_error = exc
                for leftover in tmp_dir.glob("[0-9][0-9][0-9].mp3"):
                    leftover.unlink(missing_ok=True)
                if n < MAX_CHUNKS:
                    print(
                        f"[WARN] Synthesis failed with {n} part(s) ({exc}); "
                        f"retrying with {n + 1} part(s)...",
                        flush=True,
                    )
        if body_files is None:
            raise last_error

        combine_audio_files([str(intro_file)] + body_files, output_file)

        expected_seconds = _estimated_seconds(body_text)
        actual_seconds = len(AudioSegment.from_mp3(output_file)) / 1000
        if expected_seconds > 0 and actual_seconds < expected_seconds * TRUNCATION_WARNING_RATIO:
            print(
                f"[WARN] Output audio may be truncated: got {actual_seconds:.1f}s, "
                f"expected roughly {expected_seconds:.1f}s based on word count.",
                flush=True,
            )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return output_file
