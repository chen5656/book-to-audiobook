import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from src.chapter_loader import Chapter, load_chapters
from src.text_to_speech import text_to_speech
from src.tools import combine_audio_files, split_text_into_parts

PROGRESS_FILENAME = "progress.json"


def load_progress(output_dir: Path) -> dict:
    progress_path = output_dir / PROGRESS_FILENAME
    if progress_path.exists():
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_progress(output_dir: Path, data: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / PROGRESS_FILENAME
    data["updated_at"] = datetime.now().isoformat()
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def format_chapter_filename(chapter_num: int, total_digits: int = 4) -> str:
    """
    Format chapter number as a pure numeric filename, e.g. '0001.mp3' or '0010.mp3'.
    Contains only digits before .mp3 to satisfy exact numeric naming requirements.
    """
    return f"{chapter_num:0{total_digits}d}.mp3"


def convert_single_chapter(
    chapter: Chapter,
    output_filepath: Path,
    voice: str,
    rate: str = "+0%",
) -> None:
    """
    Synthesizes a single chapter text to an MP3 file.
    Splits long chapter text into smaller parts if synthesis fails.
    """
    if output_filepath.exists() and output_filepath.stat().st_size > 0:
        return

    text = chapter.text.strip()
    if not text:
        return

    # Try synthesizing directly first
    temp_dir = output_filepath.parent / f".tmp_ch_{chapter.index}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        try:
            asyncio.run(text_to_speech(text, str(output_filepath), voice=voice, rate=rate))
        except Exception as primary_exc:
            # Fallback to chunking into parts if single call fails
            parts = split_text_into_parts(text, 4)
            part_files = []
            for idx, part in enumerate(parts, start=1):
                pf = temp_dir / f"part_{idx}.mp3"
                asyncio.run(text_to_speech(part, str(pf), voice=voice, rate=rate))
                part_files.append(str(pf))
            combine_audio_files(part_files, str(output_filepath))
    finally:
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def batch_convert_chapters(
    book_path: str,
    output_dir: str,
    start_chapter: int = 1,
    chapter_count: Optional[int] = None,
    voice: str = "zh-CN-YunjianNeural",
    rate: str = "+0%",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[str]:
    """
    Batch converts book chapters into individual MP3 files with progress persistence.
    """
    all_chapters = load_chapters(book_path)
    total_in_book = len(all_chapters)

    if start_chapter < 1 or start_chapter > total_in_book:
        raise ValueError(
            f"start_chapter ({start_chapter}) out of bounds. Book has {total_in_book} chapters."
        )

    end_idx = total_in_book
    if chapter_count is not None and chapter_count > 0:
        end_idx = min(start_chapter - 1 + chapter_count, total_in_book)

    selected_chapters = all_chapters[start_chapter - 1 : end_idx]
    total_selected = len(selected_chapters)

    out_dir_path = Path(output_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    progress_data = load_progress(out_dir_path)
    completed_chapters = set(progress_data.get("completed_chapters", []))

    progress_data.update({
        "book_path": str(Path(book_path).resolve()),
        "total_chapters_in_book": total_in_book,
        "start_chapter": start_chapter,
        "requested_chapter_count": chapter_count,
        "actual_selected_count": total_selected,
        "voice": voice,
        "rate": rate,
    })

    generated_files: List[str] = []
    total_digits = max(4, len(str(total_in_book)))

    for i, ch in enumerate(selected_chapters, start=1):
        filename = format_chapter_filename(ch.index, total_digits=total_digits)
        target_path = out_dir_path / filename

        msg = f"Chapter {ch.index}/{total_in_book}: {ch.title}"
        if progress_callback:
            progress_callback(i, total_selected, f"Processing {msg}...")

        # Skip if recorded as completed and file exists
        if ch.index in completed_chapters and target_path.exists() and target_path.stat().st_size > 0:
            if progress_callback:
                progress_callback(i, total_selected, f"Skipped (already done) {msg}")
            generated_files.append(str(target_path))
            continue

        start_time = time.time()
        convert_single_chapter(ch, target_path, voice=voice, rate=rate)
        elapsed = time.time() - start_time

        completed_chapters.add(ch.index)
        progress_data["completed_chapters"] = sorted(list(completed_chapters))
        save_progress(out_dir_path, progress_data)

        if progress_callback:
            progress_callback(i, total_selected, f"Completed {msg} in {elapsed:.1f}s")

        generated_files.append(str(target_path))

        # Explicit garbage collection after each chapter to keep RAM flat
        import gc
        gc.collect()

    return generated_files
