---
name: book-to-audiobook
description: Convert an epub/pdf/txt book into a narrated audiobook in any language, using edge-tts. Use when the user asks to "turn this book into an audiobook", "narrate this epub", or similar — for any book conversion request in this repository.
---

# Book to Audiobook

Converts a book file into an MP3 audiobook using free, keyless services
(`edge-tts` for speech, `deep-translator`'s `GoogleTranslator` for optional
translation — both need internet, neither needs an API key).

All operational choices (source language, target language, voice, speed,
input file, output path) are asked in this conversation, every time. Never
read from `.env` — there is nothing to configure there.

This skill is a thin conversational wrapper around `python -m src.cli`. All
actual text extraction, boundary detection, and audio synthesis is
deterministic code in `src/` — don't reimplement it, call the CLI via Bash.

## Gates

Work through these in order. Each gate ends with an explicit stop-and-wait
for the user — do not skip ahead, even if a step "looks obvious" (this
applies especially to Gate 3, Gate 5, and Gate 6, see Common Mistakes
below).

### Gate 0 — Setup

Run `python -m src.cli doctor`. If it reports missing dependencies, install
them (`pip install -r requirements.txt`) or tell the user to install
`ffmpeg` (`brew install ffmpeg` / `apt install ffmpeg`). First run can be
slow while dependencies install — say so, so it doesn't read as a hang.

### Gate 1 — Book and preferences

Ask the user for the following, **every time**, even if the original request
already implied one of them (e.g. "in Portuguese") — restate and confirm,
never infer or skip. Everything the user answers here is passed on as an
explicit parameter; nothing downstream in the pipeline infers or
auto-detects anything:

1. The book's name (not full path — look for it inside `books/private/`).
2. The book's source language (the language the text is already in).
3. Target language, or "no translation".
4. Voice — after (2)/(3) are known, run
   `python -m src.cli voices --lang <code> --json` using the relevant
   language (the target language if translating, otherwise the source
   language) and propose a sensible Neural voice from the real results for
   the user to confirm or swap. There is no hardcoded regional default, but
   this isn't a blind pick either — it's always grounded in a real query
   against the actual voice catalog.
5. Playback speed — ask as an explicit choice, not an open-ended question:
   **1x** (`+0%`, default), **1.5x** (`+50%`), **2x** (`+100%`), or **3x**
   (`+200%`). If the user wants something else, accept a custom edge-tts
   rate string. Never assume 1x without asking.

### Gate 2 — Inspect

Run `python -m src.cli inspect <path> --json`. Parse the JSON: metadata
(title/author/subtitle) and `boundary_candidates`.

Text extraction automatically strips decorative separator lines (rows of a
single repeated symbol used as scene breaks, e.g. `*      *      *      *`
or `-----` or `~ ~ ~`) and rewrites roman-numeral chapter numbers to arabic
digits (`CHAPTER IV` → `CHAPTER 4`, `CAPÍTULO XII` → `CAPÍTULO 12`) so
edge-tts pronounces them naturally instead of misreading them. This is
automatic and needs no confirmation — it's mechanical text hygiene, not a
judgment call. Report the counts from the JSON's `cleaning` field to the
user as an FYI (e.g. "removed 6 decorative lines, converted 12 chapter
numbers to digits").

### Gate 3 — Confirm the start/end cut

Print the actual `preview` text as visible prose in the chat — not just
summarized inside an AskUserQuestion option — for both the candidate you're
proposing as the start and the one you're proposing as the end. Show enough
surrounding text that the user can see whether a preface/foreword/
introduction sits between the proposed start and the first chapter.

Before asking for confirmation, explicitly check whether any
`boundary_candidates` entry has `"kind": "front_matter"` between the
proposed start and the first `chapter_heading`:
- **None found**: say so explicitly — "No preface/foreword/introduction
  detected between the start and the first chapter."
- **One or more found**: show its `preview` text and ask explicitly
  whether to keep it in the audiobook or skip straight to the first
  chapter — never decide this silently either way.

**Wait for explicit confirmation of `--start-char`/`--end-char` before
proceeding.** This is the core value of the skill — the semantic judgment
of where real content starts/ends (table of contents, dedication, preface
at the start; afterword, ads for other books at the end) that today only a
human makes. Gutenberg markers, when present, are one heuristic among
five — not an automatic answer.

### Gate 4 — Confirm title/author/subtitle

Show the metadata from Gate 2's JSON. Ask explicitly for confirmation or
correction (e.g. via AskUserQuestion) — never proceed on silence or
assumption.

### Gate 5 — Translate (if requested)

If Gate 1 chose a target language, run:

```
python -m src.cli pronunciation <path> --start-char N --end-char M \
  --source-lang <src> --translate-to <target> --json
```

(using the offsets confirmed in Gate 3). This translates the trimmed text
and caches it — the exact same cache `convert` reads from in Gate 7, so
translation only ever happens once. Read the resulting cache file
`.cache/<slug>.<start_char>-<end_char>.<target>.txt` and show the user the
actual translated prose (not just a summary) so they can judge translation
quality on its own — separately from pronunciation. **Wait for explicit
confirmation before moving to Gate 6.**

Keep this JSON response — Gate 6 reads its `flagged_tokens` without
needing a second CLI call. If no translation was requested, skip this gate
entirely and go straight to Gate 6.

### Gate 6 — Review pronunciation

This same `pronunciation` call also flags pronunciation-risky tokens **in
the translated text itself** (if Gate 5 ran), since that's what actually
gets spoken — reviewing the original-language text would miss whatever the
translation introduced or changed. If no translation was requested, run
the same command without `--source-lang`/`--translate-to`; it flags tokens
in the original text instead.

Show the user the flagged tokens (acronyms, numbers, foreign names) with
context from `flagged_tokens`. Let them correct spellings that the TTS
voice would mispronounce:

- **Translated text**: edit the cache file directly at
  `.cache/<slug>.<start_char>-<end_char>.<target>.txt`. It's a flat
  translated string nothing else indexes into, so editing it is safe — no
  offsets to recompute afterward.
- **Original text (no translation, or fixing something translation won't
  touch)**: edit `.cache/<slug>.txt` instead. This *does* shift character
  offsets if the edit changes text length anywhere before `end_char` — after
  editing, re-run `inspect` and reconfirm `--start-char`/`--end-char` (Gate
  3) rather than reusing the old numbers.

This is a **text** review, not a phonetic dictionary — same pattern as
`pitch-video-studio`.

### Gate 7 — Convert

Only after Gates 1-6 are confirmed. If translation was requested, Gate 5
already populated the translation cache, so this step is just audio
synthesis — no re-translation, no extra wait:

```
python -m src.cli convert <path> \
  --start-char <N> --end-char <M> \
  --voice <voice> --source-lang <lang> --rate <rate> [--translate-to <lang>] \
  --output <output.mp3>
```

### Gate 8 — Review the result

Report the output file's size/duration to the user. `convert` prints its own
`[WARN]` line if the output audio looks truncated relative to the expected
word-count-based duration — surface that warning to the user verbatim if it
appears, don't just report size/duration as if everything were fine. Ask
them to listen and confirm it sounds right.

## Common Mistakes

- Treating the table of contents or a Gutenberg marker as automatically
  "the start" without showing the preview to the user (skips Gate 3).
- Jumping straight to `convert` without having shown boundary candidates or
  pronunciation flags — always show Gate 3 and Gate 6 output first.
- Reading voice/language/paths from `.env` — there is no operational config
  file; always ask in the conversation.
- Confusing a preface/dedication (`front_matter`) with the table of
  contents (`table_of_contents`) — they need different treatment; read the
  `preview` field, don't guess from `kind` alone.
- Assuming any default voice or target language instead of deriving the
  voice suggestion from the language the user actually confirmed.
- Skipping the explicit speed ask, or asking it open-ended instead of as a
  1x/1.5x/2x/3x choice, because 1x seems obvious.
- Skipping the explicit preface/intro check at Gate 3 — silently keeping or
  dropping front matter without asking, or not saying anything when none
  is detected.
- Treating decorative-line/roman-numeral cleaning (Gate 2) as something to
  ask about — it's automatic; only *report* the counts, don't gate on it.
- Showing too little surrounding text at Gate 3 to judge whether a
  preface/foreword should be included or skipped.
- Running Gate 6's `pronunciation` without `--source-lang`/`--translate-to`
  when a translation was requested — that flags risky tokens in the
  original text, not the translated text that actually gets spoken.
- Running Gate 6 (pronunciation) without first completing Gate 5
  (translate) when a translation was requested — pronunciation must
  reflect the text that will actually be spoken.
- Editing the wrong cache file at Gate 6: the flat translated cache needs no
  offset recompute, but editing the original-text cache does.
