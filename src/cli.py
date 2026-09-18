import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from src.boundary import find_boundary_candidates, trim_to_boundaries
from src.cleaning import clean_text
from src.metadata import extract_title_author
from src.pipeline import convert_book_to_audio
from src.pronunciation import flag_risky_tokens
from src.text_cache import cache_path_for, read_or_extract, read_or_extract_raw, read_or_translate
from src.text_to_speech import list_voices

_REQUIRED_MODULES = ("edge_tts", "ebooklib", "fitz", "bs4", "deep_translator", "pydub", "tqdm")


def cmd_doctor(args) -> int:
    problems = []
    if shutil.which("ffmpeg") is None:
        problems.append("ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`).")
    for module_name in _REQUIRED_MODULES:
        try:
            __import__(module_name)
        except ImportError:
            problems.append(f"Python package missing: {module_name}. Run `pip install -r requirements.txt`.")

    if problems:
        for problem in problems:
            print(f"[FAIL] {problem}")
        return 1

    print("[OK] All dependencies found.")
    return 0


def cmd_inspect(args) -> int:
    fmt = args.format
    text, cleaning_stats = clean_text(read_or_extract_raw(args.book_path, format=fmt))
    metadata = extract_title_author(args.book_path, format=fmt)
    candidates = find_boundary_candidates(text)

    result = {
        "book_path": args.book_path,
        "format": fmt or Path(args.book_path).suffix.lstrip(".").lower(),
        "text_path": str(cache_path_for(args.book_path)),
        "char_count": len(text),
        "metadata": {
            "title": metadata.title,
            "author": metadata.author,
            "subtitle": metadata.subtitle,
        },
        "cleaning": cleaning_stats,
        "boundary_candidates": [
            {
                "char_offset": c.char_offset,
                "kind": c.kind,
                "matched_text": c.matched_text,
                "preview": c.preview,
            }
            for c in candidates
        ],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Title: {metadata.title}\nAuthor: {metadata.author}\nChars: {len(text)}")
        for c in candidates:
            print(f"  [{c.kind}] @ {c.char_offset}: {c.matched_text!r}")

    return 0


def cmd_pronunciation(args) -> int:
    if args.translate_to and not args.source_lang:
        print("[FAIL] --translate-to requires --source-lang.", file=sys.stderr)
        return 1

    text = read_or_extract(args.book_path)
    try:
        excerpt = trim_to_boundaries(text, args.start_char, args.end_char)
    except ValueError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    if args.translate_to:
        # Flag the text that will actually be spoken (post-translation), reusing
        # the same cache `convert` reads from, so translation only happens once.
        excerpt = read_or_translate(
            args.book_path, args.start_char, args.end_char,
            args.source_lang, args.translate_to, excerpt,
        )
        flagged = flag_risky_tokens(excerpt)
    else:
        flagged = flag_risky_tokens(excerpt)
        for flag in flagged:
            flag["char_offset"] += args.start_char

    result = {
        "start_char": args.start_char,
        "end_char": args.end_char,
        "translated_to": args.translate_to,
        "flagged_tokens": flagged,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for flag in flagged:
            print(f"  [{flag['reason']}] {flag['token']!r} @ {flag['char_offset']}")

    return 0


def cmd_convert(args) -> int:
    if Path(args.output).exists():
        print(f"[FAIL] {args.output} already exists.", file=sys.stderr)
        return 1

    convert_book_to_audio(
        book_path=args.book_path,
        start_char=args.start_char,
        end_char=args.end_char,
        output_file=args.output,
        voice=args.voice,
        translate_source=args.source_lang,
        rate=args.rate,
        translate_to=args.translate_to,
    )
    print(f"[OK] Audiobook saved to {args.output}")
    return 0


def cmd_voices(args) -> int:
    voices = asyncio.run(list_voices(args.lang))

    if args.json:
        print(json.dumps(voices, ensure_ascii=False, indent=2))
    else:
        for v in voices:
            print(f"  {v['ShortName']} [{v['Gender']}] {v['Locale']}")

    return 0


def cmd_chapter_convert(args) -> int:
    from src.chapter_pipeline import batch_convert_chapters

    def _progress(current: int, total: int, msg: str):
        print(f"[{current}/{total}] {msg}")

    files = batch_convert_chapters(
        book_path=args.book_path,
        output_dir=args.output_dir,
        start_chapter=args.start_chapter,
        chapter_count=args.chapter_count,
        voice=args.voice,
        rate=args.rate,
        progress_callback=_progress,
    )
    print(f"[OK] Processed {len(files)} chapters in {args.output_dir}")
    return 0


def cmd_copy_to_device(args) -> int:
    from src.copier import copy_audio_files_to_device

    def _progress(current: int, total: int, msg: str):
        print(f"[{current}/{total}] {msg}")

    files = copy_audio_files_to_device(
        source_dir=args.source_dir,
        target_dir=args.target_dir,
        progress_callback=_progress,
    )
    print(f"[OK] Copied {len(files)} audio files to {args.target_dir}")
    return 0


def cmd_gui_generator(args) -> int:
    from src.gui_generator import main as run_generator_gui
    run_generator_gui()
    return 0


def cmd_gui_copier(args) -> int:
    from src.gui_copier import main as run_copier_gui
    run_copier_gui()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="book-to-audiobook")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor").set_defaults(func=cmd_doctor)

    p_inspect = subparsers.add_parser("inspect")
    p_inspect.add_argument("book_path")
    p_inspect.add_argument("--format", default=None)
    p_inspect.add_argument("--json", action="store_true")
    p_inspect.set_defaults(func=cmd_inspect)

    p_pronunciation = subparsers.add_parser("pronunciation")
    p_pronunciation.add_argument("book_path")
    p_pronunciation.add_argument("--start-char", type=int, required=True)
    p_pronunciation.add_argument("--end-char", type=int, required=True)
    p_pronunciation.add_argument("--source-lang", default=None)
    p_pronunciation.add_argument("--translate-to", default=None)
    p_pronunciation.add_argument("--json", action="store_true")
    p_pronunciation.set_defaults(func=cmd_pronunciation)

    p_convert = subparsers.add_parser("convert")
    p_convert.add_argument("book_path")
    p_convert.add_argument("--start-char", type=int, required=True)
    p_convert.add_argument("--end-char", type=int, required=True)
    p_convert.add_argument("--voice", required=True)
    p_convert.add_argument("--source-lang", required=True)
    p_convert.add_argument("--rate", default="+0%")
    p_convert.add_argument("--translate-to", default=None)
    p_convert.add_argument("--output", required=True)
    p_convert.set_defaults(func=cmd_convert)

    p_voices = subparsers.add_parser("voices")
    p_voices.add_argument("--lang", default=None)
    p_voices.add_argument("--json", action="store_true")
    p_voices.set_defaults(func=cmd_voices)

    p_chap = subparsers.add_parser("chapter-convert")
    p_chap.add_argument("book_path")
    p_chap.add_argument("--output-dir", required=True)
    p_chap.add_argument("--start-chapter", type=int, default=1)
    p_chap.add_argument("--chapter-count", type=int, default=None)
    p_chap.add_argument("--voice", default="zh-CN-YunjianNeural")
    p_chap.add_argument("--rate", default="+0%")
    p_chap.set_defaults(func=cmd_chapter_convert)

    p_copy = subparsers.add_parser("copy-to-device")
    p_copy.add_argument("--source-dir", required=True)
    p_copy.add_argument("--target-dir", required=True)
    p_copy.set_defaults(func=cmd_copy_to_device)

    subparsers.add_parser("gui-generator").set_defaults(func=cmd_gui_generator)
    subparsers.add_parser("gui-copier").set_defaults(func=cmd_gui_copier)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())