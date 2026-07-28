# book-to-audiobook

Converte um livro (epub/pdf/txt) em audiobook narrado em pt-BR (ou no idioma
original, sem tradução) — 100% gratuito, sem chave de API. Usa
[`edge-tts`](https://github.com/rany2/edge-tts) pra síntese de voz e o
[`deep-translator`](https://github.com/nidhaloff/deep-translator)
`GoogleTranslator` pra tradução opcional — ambos gratuitos, mas exigem
internet.

## Como usar (via Claude Code)

Esta é uma [Claude Code Skill](https://code.claude.com/docs/en/skills)
pública. Não tem passo de instalação separado:

1. Clone este repositório.
2. Abra o Claude Code **na raiz da pasta clonada**.
3. Arraste o epub/pdf/txt do livro pra `books/private/` (nunca versionado,
   ver [`books/private/README.md`](books/private/README.md)).
4. Peça: *"transforme `meu-livro.epub` em audiobook"*. A skill
   `book-to-audiobook` conduz a conversa em etapas (Gates): confere
   dependências, pergunta idioma/voz, mostra onde o conteúdo real
   começa/termina pra você confirmar, mostra trechos com pronúncia
   arriscada pra revisão, e só então gera o mp3.

Pra testar sem precisar de um livro seu: `books/alice.epub` já vem no repo
(*Alice's Adventures in Wonderland*, domínio público) — peça *"transforme
books/alice.epub em audiobook"* e siga os Gates.

A primeira execução pode demorar um pouco mais — a skill confere/instala
dependências sozinha (`doctor`). Isso não é travamento.

## Pré-requisitos

- Python 3.10+
- [`ffmpeg`](https://ffmpeg.org/) instalado no sistema (`brew install ffmpeg`
  no macOS, `apt install ffmpeg` no Linux) — usado pelo `pydub` pra
  manipular áudio.
- Internet (edge-tts e GoogleTranslator são gratuitos, mas online).

```bash
pip install -r requirements.txt
```

Para rodar os testes:

```bash
pip install -r requirements-dev.txt
pytest
```

## Uso via linha de comando (sem o assistente)

O mesmo pipeline também roda direto por `src/cli.py`, se você preferir
controlar os parâmetros manualmente:

```bash
# Confere se ffmpeg e as libs Python estão presentes
python -m src.cli doctor

# Extrai texto + metadados + candidatos de início/fim do conteúdo real
python -m src.cli inspect books/alice.epub --json

# Sinaliza siglas/números/nomes estrangeiros pra revisar pronúncia
python -m src.cli pronunciation books/alice.epub \
  --start-char 2100 --end-char 158000 --json

# Gera o audiobook (offsets decididos a partir do inspect acima)
python -m src.cli convert books/alice.epub \
  --start-char 2100 --end-char 158000 \
  --voice pt-BR-AntonioNeural --translate-to portuguese \
  --output alice.mp3
```

`--start-char`/`--end-char` são sempre explícitos — não existe corte
automático de início/fim sem confirmação humana. Voz, idioma de destino,
arquivo de entrada e pasta de saída também são sempre parâmetros
explícitos: nada é lido de `.env` (ver [`.env.example`](.env.example)).

## Estrutura

```text
src/
  loaders/          epub, pdf, txt -> texto
  text_cache.py      cache do texto extraído (evita reprocessar)
  boundary.py         candidatos de início/fim do conteúdo real
  metadata.py           título/autor/subtítulo
  intro.py                texto falado de abertura
  pronunciation.py         sinaliza trechos de pronúncia arriscada
  translate.py               tradução em lotes
  text_to_speech.py            texto -> mp3 (edge-tts)
  tools.py                       divide texto / combina mp3s
  pipeline.py                     orquestra tudo (convert_book_to_audio)
  cli.py                            doctor | inspect | pronunciation | convert
.claude/skills/book-to-audiobook/  a Skill/plugin do Claude Code
books/alice.epub          fixture de demo (domínio público, Project Gutenberg)
```
