# Design: lacunas do plano de modernização (book-to-audiobook)

Data: 2026-07-28
Ponto de partida: [`docs/modernization-plan.md`](../../modernization-plan.md) (Prompt 2 da sequência recomendada lá).
Este documento não substitui o plano — fecha decisões que ele deixava em aberto. Onde não há menção aqui, vale o que já está em `modernization-plan.md`.

## Decisões fechadas nesta sessão

### 1. Texto extraído — cache em disco, não stdout

`inspect` extrai 200k–1,2M caracteres por livro. Colocar isso no JSON de stdout estouraria o contexto do assistente. Decisão: `inspect` grava o texto extraído em `.cache/<slug-do-nome-do-arquivo>.txt` e devolve só `text_path` apontando pra lá — nunca o texto inteiro embutido no JSON.

`.cache/` entra no `.gitignore` (artefato derivado, mesmo tratamento de `books/private/*`).

### 2. Módulo novo: `src/text_cache.py`

Não estava no plano original — motivado pela decisão acima, já que `inspect`, o novo `pronunciation` (item 3) e `convert` precisam do mesmo texto extraído sem reprocessar PDF/epub 3 vezes.

```python
cache_path_for(book_path) -> Path        # .cache/<slug>.txt, determinístico
read_or_extract(book_path, format=None) -> str
    # lê do cache se existir; senão chama loaders.load_book() e grava
```

Path é só o slug do nome do arquivo (não hash de conteúdo).
`ponytail: colide se dois livros diferentes tiverem o mesmo nome de arquivo — renomear o arquivo resolve, não vale complexidade de hashing pra um usuário convertendo um livro de cada vez.`

### 3. Gate 5 (revisão de pronúncia) precisa de subcomando próprio

O plano só listava `doctor | inspect | convert` em `cli.py`, mas a tabela de Gates da Skill exige rodar `pronunciation.flag_risky_tokens` em algum momento — sem comando, o assistente não tem como chamar isso via `Bash`. Decisão: 4º subcomando.

```
pronunciation <arquivo> --start-char N --end-char M [--json]
```

Sinaliza em cima do texto **original** (pré-tradução), não do texto traduzido. Siglas, números e nomes próprios tendem a sobreviver à tradução; evita uma 2ª chamada de rede ao `GoogleTranslator` só pra revisão, e mantém o Gate 5 rápido e offline-friendly.

### 4. `flag_risky_tokens` devolve posição, não só o token

O plano descrevia `flag_risky_tokens(text) -> list[str]`. Decisão: isso é inútil pra revisão humana num texto de 100k+ caracteres sem dizer *onde* está o token. Assinatura revisada:

```python
flag_risky_tokens(text) -> list[dict]
# cada item: {"token": str, "reason": "acronym"|"number"|"foreign_name", "char_offset": int, "context": str}
```

`reason` é enum fechado de 3 valores, direto das heurísticas já descritas no plano (siglas maiúsculas / números / nomes próprios não-portugueses).

### 5. `BoundaryCandidate.kind` — enum fechado de 5 valores

O plano citava 4 heurísticas (marcador Gutenberg, capítulo, sumário/TOC, matéria final). Adicionado um 5º: `front_matter`, pra cobrir dedicatória/prefácio/epígrafe que não é TOC nem capítulo — caso real do poema "All in the golden afternoon" antes do Capítulo 1 em *Alice's Adventures in Wonderland* (o livro de demo do próprio plano).

```
gutenberg_marker | chapter_heading | table_of_contents | back_matter | front_matter
```

### 6. JSON exato de `inspect --json`

```json
{
  "book_path": "books/private/alice.epub",
  "format": "epub",
  "text_path": ".cache/alice.txt",
  "char_count": 164221,
  "metadata": { "title": "Alice's Adventures in Wonderland", "author": "Lewis Carroll", "subtitle": null },
  "boundary_candidates": [
    { "char_offset": 812, "kind": "gutenberg_marker", "matched_text": "*** START OF THE PROJECT GUTENBERG EBOOK ***", "preview": "...200 chars ao redor..." },
    { "char_offset": 1450, "kind": "front_matter", "matched_text": "All in the golden afternoon", "preview": "..." },
    { "char_offset": 2100, "kind": "chapter_heading", "matched_text": "CHAPTER I", "preview": "..." }
  ]
}
```

Default de `inspect` (sem `--json`) é texto legível pra humano rodando manualmente no terminal; o assistente sempre passa `--json` explicitamente pra parsear.

### 7. JSON exato de `pronunciation --json`

```json
{
  "start_char": 2100, "end_char": 158000,
  "flagged_tokens": [
    { "token": "ISBN", "reason": "acronym", "char_offset": 2340, "context": "...80 chars ao redor..." },
    { "token": "Lacie", "reason": "foreign_name", "char_offset": 5210, "context": "..." }
  ]
}
```

### 8. `text_to_speech.py` — erro explícito, sem parâmetro novo

Hoje faz `print` + `return` silencioso se `output_file` já existe (falha engolida). Decisão: levanta `FileExistsError` sempre, sem adicionar parâmetro `overwrite`. Quem quiser regerar apaga o arquivo antes de chamar.

`convert` (cli.py) replica a mesma filosofia no nível do comando: checa se `--output` já existe **antes** de rodar qualquer TTS, e falha cedo — evita queimar minutos de síntese só pra barrar na escrita do arquivo final combinado.

### 9. `translate.py` — renomeia função interna pro inglês

`translate()` já estava sendo modificada pelo plano (source/target viram parâmetros explícitos, sem default de `.env`). Já que o arquivo ia ser tocado mesmo, a função interna `dividir_texto_em_frases` (nome herdado do código legado, em português) é renomeada pra `split_into_sentences`, alinhando com o resto dos módulos novos (`load_book`, `find_boundary_candidates`, etc. — identificadores em inglês, conforme preferência global do usuário). `translate.py` fica assim:

```python
translate(texto, source, target, limite=4000)   # assinatura pública inalterada, source/target sem default
split_into_sentences(texto)                       # renomeado de dividir_texto_em_frases
```

`tools.py` e `text_to_speech.py` (fora do fix do item 8) **não** são tocados além do que o plano já pedia — nomes em português mantidos onde o plano não pediu mudança.

## Arquitetura final de `src/` (delta sobre o plano)

```
src/
  loaders/                    # inalterado — ver modernization-plan.md
  text_cache.py               # NOVO — item 2
  boundary.py                 # kind vira enum de 5 valores — item 5
  metadata.py                 # inalterado
  intro.py                    # inalterado
  pronunciation.py            # flag_risky_tokens devolve list[dict], não list[str] — item 4
  translate.py                # split_into_sentences (renomeado) + source/target explícitos — item 9
  text_to_speech.py           # FileExistsError explícito, sem overwrite= — item 8
  tools.py                    # inalterado
  pipeline.py                 # inalterado (orquestra os módulos acima)
  cli.py                      # 4 subcomandos agora: doctor | inspect | pronunciation | convert — itens 3, 6, 7
```

## Não fechado / fora de escopo desta sessão

Nada ficou pendente das lacunas levantadas — todas as ambiguidades identificadas no plano original (formato JSON, módulos novos, pontos incompletos) foram resolvidas acima. Detalhamento de critério de aceite por módulo, ordem de implementação e testes fica pro próximo passo (`writing-plans`, Prompt 3 da sequência — sessão separada, conforme o próprio plano prevê).