# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Setup:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

`ffmpeg` must also be on `PATH` (`brew install ffmpeg` / `apt install ffmpeg`) — `pydub` shells out to it for audio conversion/concatenation.

Tests:

```bash
pytest                                     # full suite
pytest tests/test_pipeline.py              # one file
pytest tests/test_pipeline.py::test_name -v  # one test
```

There is no lint/format tool configured (`requirements-dev.txt` only has `pytest`) — don't invent `ruff`/`flake8`/`black` commands that aren't set up.

CLI (the same entry point the Claude Code skill drives via Bash — see Architecture below):

```bash
python -m src.cli doctor
python -m src.cli inspect <path> --json
python -m src.cli voices --lang <code> --json
python -m src.cli pronunciation <path> --start-char N --end-char M [--source-lang X --translate-to Y] --json
python -m src.cli convert <path> --start-char N --end-char M --voice V --source-lang X --rate R [--translate-to Y] --output out.mp3
```

## Architecture

### A conversational skill wraps a deterministic CLI

`.claude/skills/book-to-audiobook/SKILL.md` defines an 8-gate conversation (setup → book/preferences → inspect → confirm start/end cut → confirm metadata → translate → review pronunciation → convert → review result). The skill does no text processing itself — it only shells out to `python -m src.cli <subcommand>` and surfaces real output (boundary previews, flagged tokens, translated prose) to the user at each gate before proceeding. All actual logic lives in `src/`.

When changing CLI JSON output shape, check `SKILL.md` first — it parses specific keys (`boundary_candidates[].kind`/`preview`, `cleaning`, `flagged_tokens`) and the gate flow depends on them.

### No hidden defaults, anywhere

Every operational parameter — voice, source/target language, start/end char offsets, playback rate — is an explicit CLI argument on every call. Nothing is read from `.env` (`.env.example` is currently just a placeholder for a future paid TTS/OCR API key) or silently inferred. The only thing persisted across calls is the extraction/translation cache described below. Keep this property when adding parameters: no auto-detection, no stored "last used" defaults.

### Extraction → clean → boundary → translate, all keyed through `src/text_cache.py`

- `read_or_extract_raw` / `read_or_extract` dispatch to `src/loaders/` (epub/pdf/txt, chosen by extension in `loaders/__init__.py`) and cache the raw extracted text at `.cache/<slug>.txt`, keyed only by the book's filename slug — re-running `inspect` or `convert` never re-parses the source file.
- `src/cleaning.py` strips decorative separator lines (repeated-symbol scene breaks) and rewrites roman-numeral chapter headings to digits, returning stats (`decorative_lines_removed`, `roman_chapters_converted`) that `cli.py inspect` reports back. This runs automatically, before boundary offsets are computed, so char offsets the user confirms are against the *cleaned* text.
- `src/boundary.py` finds candidate start/end points (Gutenberg markers, chapter headings, table of contents, front/back matter) and applies the human-confirmed `--start-char`/`--end-char`.
- `read_or_translate` caches the *translated, already-trimmed* text at `.cache/<slug>.<start_char>-<end_char>.<target>.txt`, keyed by the confirmed offsets and target language. This is the mechanism that lets the pronunciation gate and the convert step share one translation instead of doing it twice — both call this same function with the same key.
- `src/pronunciation.py` flags acronyms/numbers/capitalized-mid-sentence words in whatever text will actually be spoken (the translated cache if a translation was requested, the cleaned/trimmed source otherwise) — never the raw untranslated source when translation is in play.

### Synthesis (`src/pipeline.py`)

`convert_book_to_audio` builds a short intro line from metadata (`src/metadata.py` + `src/intro.py`), synthesizes intro and body separately, then concatenates them (`src/tools.py:combine_audio_files`). Body text is split into N word-safe chunks (`tools.py:split_text_into_parts`) and synthesized part-by-part through edge-tts (`src/text_to_speech.py`). If synthesis fails partway through, it retries with progressively more/smaller chunks (the `MAX_CHUNKS` loop) instead of failing outright. After combining, output duration is sanity-checked against a words-per-minute estimate and a `[WARN]` (not an exception) is printed if the audio looks truncated — see the `# ponytail:` comments in `pipeline.py`, which mark the known ceilings of these heuristics (chunk count, WPM estimate) and what to do if they start false-positiving.

### Metadata extraction is format-dependent

`src/metadata.py` reads real EPUB `DC` metadata (title/author/subtitle) for `.epub`. For `.pdf`/`.txt` there is no such metadata, so it falls back to "first non-blank line of text as title" with no author/subtitle.
