---
name: book-to-audiobook
description: Convert an epub/pdf/txt book into a narrated pt-BR (or original-language) audiobook. Use when the user asks to "turn this book into an audiobook", "narrate this epub", or similar — for any book conversion request in this repository.
---

# Book to Audiobook

Converts a book file into an MP3 audiobook using free, keyless services
(`edge-tts` for speech, `deep-translator`'s `GoogleTranslator` for optional
translation — both need internet, neither needs an API key).

All operational choices (voice, target language, input file, output path)
are asked in this conversation, every time. Never read from `.env` — there
is nothing to configure there.

This skill is a thin conversational wrapper around `python -m src.cli`. All
actual text extraction, boundary detection, and audio synthesis is
deterministic code in `src/` — don't reimplement it, call the CLI via Bash.

## Gates

Work through these in order. Each gate ends with an explicit stop-and-wait
for the user — do not skip ahead, even if a step "looks obvious" (this
applies especially to Gate 3 and Gate 5, see Common Mistakes below).

### Gate 0 — Setup

Run `python -m src.cli doctor`. If it reports missing dependencies, install
them (`pip install -r requirements.txt`) or tell the user to install
`ffmpeg` (`brew install ffmpeg` / `apt install ffmpeg`). First run can be
slow while dependencies install — say so, so it doesn't read as a hang.

### Gate 1 — Book and preferences

Ask the user for:
- The book's name (not full path — look for it inside `books/private/`).
- Target language, or "no translation".
- Voice (offer the default `pt-BR-AntonioNeural` if they have no preference).

### Gate 2 — Inspect

Run `python -m src.cli inspect <path> --json`. Parse the JSON: metadata
(title/author/subtitle) and `boundary_candidates`.

### Gate 3 — Confirm the start/end cut

Show the user each boundary candidate's `preview` and `kind`. **Wait for
explicit confirmation of `--start-char`/`--end-char` before proceeding.**
This is the core value of the skill — the semantic judgment of where real
content starts/ends (table of contents, dedication, preface at the start;
afterword, ads for other books at the end) that today only a human makes.
Gutenberg markers, when present, are one heuristic among five — not an
automatic answer.

### Gate 4 — Confirm title/author/subtitle

Show the metadata from Gate 2's JSON. Let the user correct it. This feeds
the spoken intro (e.g. "Alice's Adventures in Wonderland. De Lewis
Carroll.").

### Gate 5 — Review pronunciation

Run `python -m src.cli pronunciation <path> --start-char N --end-char M --json`
(using the offsets confirmed in Gate 3). Show the user the flagged tokens
(acronyms, numbers, foreign names) with context. Let them correct spellings
that the TTS voice would mispronounce. This is a **text** review, not a
phonetic dictionary — same pattern as `pitch-video-studio`.

### Gate 6 — Convert

Only after Gates 1-5 are confirmed:

```
python -m src.cli convert <path> \
  --start-char <N> --end-char <M> \
  --voice <voice> [--translate-to <lang>] \
  --output <output.mp3>
```

### Gate 7 — Review the result

Report the output file's size/duration to the user. Ask them to listen and
confirm it sounds right.

## Common Mistakes

- Treating the table of contents or a Gutenberg marker as automatically
  "the start" without showing the preview to the user (skips Gate 3).
- Jumping straight to `convert` without having shown boundary candidates or
  pronunciation flags — always show Gate 3 and Gate 5 output first.
- Reading voice/language/paths from `.env` — there is no operational config
  file; always ask in the conversation.
- Confusing a preface/dedication (`front_matter`) with the table of
  contents (`table_of_contents`) — they need different treatment; read the
  `preview` field, don't guess from `kind` alone.