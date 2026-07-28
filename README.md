# book-to-audiobook

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/price-100%25%20free-brightgreen.svg" alt="100% free">
  <img src="https://img.shields.io/badge/Claude%20Code-Skill-6E56CF.svg" alt="Claude Code Skill">
  <img src="https://img.shields.io/github/stars/gomesfellipe/book-to-audiobook?style=flat" alt="GitHub stars">
</p>

<p align="center">
  Turn any epub / pdf / txt into a narrated audiobook, in any language —<br>
  100% free, no API key.
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#cli-usage-without-the-assistant">CLI usage</a> ·
  <a href="#structure">Structure</a> ·
  <a href="#contributing--development">Contributing</a>
</p>

---

Uses [`edge-tts`](https://github.com/rany2/edge-tts) (Microsoft's free Neural
voices) for speech synthesis and
[`deep-translator`](https://github.com/nidhaloff/deep-translator)'s
`GoogleTranslator` for optional translation — both free, but require
internet.

## Why

- 🆓 **100% free, no API key** — no OpenAI/ElevenLabs/Polly bill, ever.
- 🌍 **Any source/target language** — translation is optional; hundreds of
  real Neural voices to pick from.
- ✅ **Human-in-the-loop, not a black box** — you confirm where the real
  content starts and ends, the title/author, and review every
  pronunciation-risky word before a single second of audio gets generated.
- ⚡ **Smart caching** — extraction and translation are cached, so
  regenerating with a different voice or speed is instant, no
  re-processing.
- 📚 **epub / pdf / txt in, one `.mp3` out.**

## How it works

Ask Claude Code (opened at the root of this repo) to turn a book into an
audiobook. The `book-to-audiobook` skill drives the conversation through 8
Gates — nothing is inferred or defaulted silently, everything below is
confirmed by you before the pipeline moves on:

```mermaid
flowchart LR
    A["0 · Setup"] --> B["1 · Book & preferences"]
    B --> C["2 · Inspect"]
    C --> D["3 · Confirm start/end cut"]
    D --> E["4 · Confirm metadata"]
    E --> F["5 · Translate"]
    F --> G["6 · Review pronunciation"]
    G --> H["7 · Convert"]
    H --> I["8 · Review result"]
```

Voice, source/target language, speed, and the exact start/end of the "real"
content (skipping tables of contents, front matter, back-of-book ads) are
always explicit choices made in the conversation — never auto-detected.

## Quick start

This is a public [Claude Code Skill](https://code.claude.com/docs/en/skills)
— there's no separate install step:

1. Clone this repository.
2. Open Claude Code **at the root of the cloned folder**.
3. Drop the epub/pdf/txt of the book into `books/private/` (never
   versioned, see [`books/private/README.md`](books/private/README.md)).
4. Ask: *"turn `my-book.epub` into an audiobook"*. The skill checks
   dependencies, asks for source/target language, voice and speed, shows
   where the real content starts/ends for you to confirm, shows
   pronunciation-risky snippets for review, and only then generates the
   mp3.

No book on hand? `books/alice.epub` ships in the repo (*Alice's Adventures
in Wonderland*, public domain) — ask *"turn books/alice.epub into an
audiobook"* and follow the Gates.

The first run can take a bit longer — the skill checks/installs
dependencies on its own (`doctor`). That's not a hang.

## Requirements

- Python 3.10+
- [`ffmpeg`](https://ffmpeg.org/) installed on the system (`brew install ffmpeg`
  on macOS, `apt install ffmpeg` on Linux) — used by `pydub` to manipulate
  audio.
- Internet (edge-tts and GoogleTranslator are free, but online).

```bash
pip install -r requirements.txt
```

To run the tests:

```bash
pip install -r requirements-dev.txt
pytest
```

## CLI usage (without the assistant)

The same pipeline also runs directly via `src/cli.py`, if you'd rather
control the parameters manually:

```bash
# Check that ffmpeg and the Python libs are present
python -m src.cli doctor

# Extract text + metadata + start/end boundary candidates for the real
# content. Also reports cleaning stats (decorative lines stripped, roman
# numeral chapter headings converted to digits — both automatic).
python -m src.cli inspect books/alice.epub --json

# List real edge-tts voices for a given language, e.g. Portuguese
python -m src.cli voices --lang pt --json

# Flag acronyms/numbers/foreign names to review for pronunciation.
# Add --source-lang/--translate-to to review (and cache) the *translated*
# text instead — that's what actually gets spoken if you're translating.
python -m src.cli pronunciation books/alice.epub \
  --start-char 2100 --end-char 158000 \
  [--source-lang en --translate-to <lang>] --json

# Generate the audiobook (offsets decided from the inspect above). If a
# translation was requested, the pronunciation step above already cached
# it, so this just synthesizes audio.
python -m src.cli convert books/alice.epub \
  --start-char 2100 --end-char 158000 \
  --voice <voice-id> --source-lang en --rate +0% [--translate-to <lang>] \
  --output alice.mp3
```

`--start-char`/`--end-char` are always explicit — there's no automatic
start/end cut without human confirmation. Voice, source/target language,
speed, input file, and output folder are also always explicit parameters:
nothing is read from `.env` (see [`.env.example`](.env.example)).

Translated text is cached in `.cache/` alongside the extracted source text,
keyed by book, confirmed offsets, and target language, so re-running
`convert` (e.g. just to tweak voice or speed) skips re-translating.
Temporary per-part audio files also live in `.cache/` during synthesis, not
next to the final output file.

## Structure

```text
src/
  loaders/          epub, pdf, txt -> text
  text_cache.py      cache of extracted/translated text (avoids reprocessing)
  cleaning.py         strips decorative lines, normalizes roman numerals
  boundary.py           start/end candidates for the real content
  metadata.py             title/author/subtitle
  intro.py                  spoken opening text
  pronunciation.py           flags pronunciation-risky snippets
  translate.py                 batched translation
  text_to_speech.py              text -> mp3 (edge-tts), voice catalog lookup
  tools.py                         split text / combine mp3s
  pipeline.py                        orchestrates everything (convert_book_to_audio)
  cli.py                               doctor | inspect | pronunciation | voices | convert
.claude/skills/book-to-audiobook/  the Claude Code Skill/plugin
books/alice.epub          demo fixture (public domain, Project Gutenberg)
```

## Contributing / development

See [`CLAUDE.md`](CLAUDE.md) for the architecture overview (how the Gates in
the skill map to `src/`, the extraction/translation cache, the synthesis
retry logic) and the commands to run tests. `CLAUDE.local.md`, if present, is
personal and gitignored — it's not part of this repo's shared guidance.

## License

[MIT](LICENSE)

---

<p align="center">
  Built by <a href="https://github.com/gomesfellipe">Fellipe Gomes</a>
</p>
