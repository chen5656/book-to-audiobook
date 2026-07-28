import argparse
import json
import shutil
import sys
from pathlib import Path

from src.boundary import find_boundary_candidates, trim_to_boundaries
from src.metadata import extract_title_author
from src.pipeline import convert_book_to_audio
from src.pronunciation import flag_risky_tokens
from src.text_cache import cache_path_for, read_or_extract

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
    text = read_or_extract(args.book_path, format=fmt)
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
    text = read_or_extract(args.book_path)
    try:
        excerpt = trim_to_boundaries(text, args.start_char, args.end_char)
    except ValueError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1
    flagged = flag_risky_tokens(excerpt)
    for flag in flagged:
        flag["char_offset"] += args.start_char

    result = {
        "start_char": args.start_char,
        "end_char": args.end_char,
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
        translate_to=args.translate_to,
    )
    print(f"[OK] Audiobook saved to {args.output}")
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
    p_pronunciation.add_argument("--json", action="store_true")
    p_pronunciation.set_defaults(func=cmd_pronunciation)

    p_convert = subparsers.add_parser("convert")
    p_convert.add_argument("book_path")
    p_convert.add_argument("--start-char", type=int, required=True)
    p_convert.add_argument("--end-char", type=int, required=True)
    p_convert.add_argument("--voice", default="pt-BR-AntonioNeural")
    p_convert.add_argument("--translate-to", default=None)
    p_convert.add_argument("--output", required=True)
    p_convert.set_defaults(func=cmd_convert)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())