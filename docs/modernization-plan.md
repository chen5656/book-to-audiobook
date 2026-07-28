# Modernizar book-to-audiobook como Claude Code Skill pública

## Contexto

Este repo é um projeto pessoal legado: um pipeline manual de "livro → audiobook em pt-BR" 100% gratuito (edge-tts + deep-translator, sem chave de API), operado copiando `main.ipynb` para um notebook novo por livro e editando manualmente `inicio`/`final` (strings onde o conteúdo real começa/termina). Funciona, mas não escala e não é compartilhável: os ~14 notebooks em `examples/` têm o **texto integral de livros comerciais** (200k–1,2M caracteres cada) embutido nos outputs de célula, commitado no histórico do git.

Objetivo: transformar isso numa **Claude Code Skill pública** que qualquer pessoa possa clonar e usar — o usuário fornece um epub/pdf/html, pede ao assistente para converter, o assistente identifica os limites de início/fim do conteúdo (hoje o único passo manual), confirma com o humano, e o pipeline determinístico (já testado) gera o mp3. Sem nada pago. Sem vazar conteúdo protegido por direitos autorais.

Decisões já validadas com o usuário:
- **Git**: reiniciar histórico como orphan commit limpo; histórico antigo preservado só localmente (branch/tag não pushados), nunca vai ao remoto.
- **Notebooks de `examples/`**: apagados do repo público; a lógica genérica de cada loader é extraída para `src/loaders/` antes de apagar.
- **Ingestão generalizada, mas leve**: cogitamos [MinerU](https://github.com/opendatalab/MinerU) como motor único de ingestão (PDF/imagem/DOCX/PPTX/XLSX com OCR), mas **descartado** — exige 16GB RAM recomendados e ~20GB de disco (modelos de layout/OCR), incompatível com a máquina do usuário (8GB RAM) e com o objetivo de a skill ser leve, não um "elefante branco". Em vez disso, generalização via **dispatch unificado leve**: `src/loaders/load_book(path)` escolhe o parser certo pela extensão, cada parser é uma lib pequena e sem modelo de ML: `epub` → `ebooklib`+`BeautifulSoup` (já provado nos notebooks), `pdf` → **PyMuPDF** só (consolida os dois padrões concorrentes — `PyPDF2` e `PyMuPDF` — que coexistiam ad hoc nos notebooks antigos), `txt` → trivial. HTML é descartado como fonte suportada (era só um crawler específico do fairmlbook, não um caso genérico). OCR de PDF escaneado fica documentado como extensão *opcional* futura (`requirements-ocr.txt`, ex. `pytesseract`), não instalada por padrão — nenhum dos livros reais do usuário hoje precisa disso.
- **Livro de demo pública**: *Alice's Adventures in Wonderland* (Lewis Carroll, Project Gutenberg), por ser reconhecido mundialmente. A detecção de fronteiras **não pode se apoiar só nos marcadores exatos do Gutenberg** (`*** START/END OF THE PROJECT GUTENBERG EBOOK ***`) — isso tiraria a graça da skill, que é justamente fazer o julgamento semântico de onde o conteúdo real começa/termina (sumário, dedicatória, prefácio no início; posfácio, propaganda de outros livros no fim), igual ao que hoje só o humano faz manualmente. Os marcadores do Gutenberg entram só como **um heurístico determinístico a mais** (útil como fallback/ponto de partida), não como a resposta pronta.

## Diagnóstico do código atual (para reaproveitar, não redescobrir)

- `src/tools.py`: `dividir_texto_em_partes` e `combinar_arquivos_audio` — já corretos e pequenos, mantêm-se como estão.
- `src/translate.py`: `translate()` usa `GoogleTranslator` (gratuito) mas **hardcoda** `source='auto', target='portuguese'` no corpo da função — não existe nem parâmetro pra idioma de destino. Corrigir para receber `source`/`target` como argumentos explícitos (sem default vindo de `.env` — ver decisão sobre configuração abaixo).
- `src/text_to_speech.py`: se `output_file` já existe, faz `print` + `return` **silencioso** em vez de erro — perigoso numa pipeline automatizada (falha engolida). Corrigir para erro explícito (ou `overwrite=True`).
- Padrões de loader duplicados em cada notebook de `examples/`, nunca extraídos para `src/`:
  - **epub**: `ebooklib.epub.read_epub` → itera `ITEM_DOCUMENT` → `BeautifulSoup(...).get_text()`, removendo `<span>` que contêm `<a>`. Mantido como loader dedicado (leve, MinerU não lê epub).
  - **pdf**: dois padrões coexistiam ad hoc (`PyPDF2` num notebook, `PyMuPDF`/fitz noutro) — consolidar em **PyMuPDF** só (ver decisão acima; MinerU foi cogitado e descartado por peso). Remover `PyPDF2` de `requirements.txt`.
  - **html**: o único exemplo (`fairmlbook`) é um crawler específico daquele site — descartado, não vira loader (decisão do usuário).
- `blog_post/` contém `audiobook.mp3` derivado de um livro **CC BY-NC-ND** (cláusula "No Derivatives" veta redistribuir esse mp3) e usa fairmlbook como exemplo — contradiz a decisão de usar só Gutenberg. Recomendo remover do repo público (some para `legacy-local`, nunca pushado).
- **Configuração operacional não deve morar em `.env`**: o usuário foi explícito — `.env` deve conter *apenas chaves de API, e só se realmente necessário*. Hoje nenhuma é necessária (edge-tts e GoogleTranslator são gratuitos e sem chave). Isso muda o papel de `.env.example` — deixa de ter `BOOKS_PATH`/`OUTPUT_PATH`/`TTS_*`/`TRANSLATE_*` (removidos) e vira só um placeholder documentando que hoje nada é obrigatório, reservado pra quando/se um backend pago (TTS ou OCR) for adicionado no futuro. Voz, idioma de destino, arquivo de entrada e pasta de saída passam a ser perguntados **pelo assistente, na conversa**, no momento em que a skill é acionada (ver seção da Skill abaixo) — não configurados uma vez e esquecidos.
- `ffmpeg` é dependência de sistema real (pydub chama via subprocess) — hoje não documentada em nenhum README, precisa entrar no `doctor` do CLI e no README. Sem MinerU, a skill continua leve: `ebooklib`+`BeautifulSoup`+`PyMuPDF` somam poucos MB, rodam bem em 8GB RAM, sem download de modelo nenhum.
- `.claude/settings.json` (ainda untracked) já habilita os plugins `superpowers` e `improve` — usar os skills deles para conduzir a implementação (não pular para código direto).

## Arquitetura nova de `src/`

```
src/
  loaders/
    __init__.py              # load_book(path, format=None) -> str, dispatch por extensão
    epub_loader.py            # extraído do padrão ebooklib+BeautifulSoup já usado nos notebooks
    pdf_loader.py              # PyMuPDF (fitz), remove numeração de página via regex — leve, sem modelo de ML
    txt_loader.py                # trivial, usado em fixtures/testes
  boundary.py                # "onde no texto será o início e o fim do audiobook?" — em vez de o humano procurar
                               # manualmente a frase de início/fim (como hoje em cada notebook), essa função varre o
                               # texto extraído e devolve uma LISTA DE PONTOS SUSPEITOS: cada um é "nessa posição do
                               # texto, achei algo que parece início/fim de conteúdo real (ex: 'Capítulo 1', ou
                               # 'Sumário', ou 'Agradecimentos'), e aqui está um pedacinho do texto ao redor pra você
                               # (assistente + humano) ler e decidir se é isso mesmo". Nunca decide sozinha.
                               # find_boundary_candidates(text) -> list[BoundaryCandidate] — cada item tem:
                               #   char_offset (posição no texto), kind (que tipo de marca é), matched_text (o trecho
                               #   que bateu), preview (~200 caracteres ao redor, pra dar contexto de leitura)
                               # trim_to_boundaries(text, start_char, end_char) -> corta o texto nos dois pontos
                               # escolhidos (Gate 3 do fluxo abaixo)
                               # heurísticas regex são só PONTO DE PARTIDA, não a resposta final: marcadores Gutenberg,
                               # "capítulo/chapter N", "sumário/índice/table of contents", matéria final
                               # ("agradecimentos/acknowledgments/sobre o autor/referências/bibliography")
                               # NENHUM texto de livro embutido aqui — só regex/heurística
  metadata.py                 # extract_title_author(path, format) -> BookMetadata (title, author, subtitle) a partir de
                               # metadados do epub (ebooklib já expõe isso) ou, pra pdf/txt, das primeiras linhas extraídas
                               # + confirmação do usuário no chat; usado pra montar a intro falada
  intro.py                    # build_intro_text(metadata) -> str, inclui subtítulo quando existir
                               # (ex: "Alice no País das Maravilhas. Um conto sobre... De Lewis Carroll.")
                               # sintetizado via text_to_speech e prependido ao áudio final — feature nova pedida pelo usuário
  pronunciation.py             # flag_risky_tokens(text) -> list[str]: heurística leve (regex) sinalizando siglas em
                               # caixa alta, números, nomes próprios não-portugueses — NÃO corrige sozinho, só aponta
                               # trechos pro usuário revisar/editar no Gate 5 (mesmo padrão do pitch-video-studio:
                               # correção de pronúncia é revisão de texto pelo humano, não dicionário fonético/SSML)
  translate.py                # translate(texto, source, target, limite=4000) — source/target agora são parâmetros
                               # explícitos (sem default vindo de .env), preenchidos pela resposta do usuário na conversa
  text_to_speech.py            # mesma assinatura, erro explícito se output_file existir (corrige silêncio atual)
  tools.py                      # mantido como está (dividir_texto_em_partes, combinar_arquivos_audio)
  pipeline.py                    # convert_book_to_audio(...) orquestra loader -> metadata -> boundary.trim ->
                                   # translate opcional -> intro -> tools.dividir -> text_to_speech por parte -> combinar
  cli.py                          # subcomandos: doctor | inspect <arquivo> [--json] |
                                   # convert <arquivo> --start-char N --end-char M --voice ... [--translate-to ...] --output out.mp3
                                   # (todos os parâmetros de voz/idioma/saída vêm de flags explícitas na chamada, nunca de .env)
```

Ponto central do design: `cli.py convert` **exige** `--start-char`/`--end-char` explícitos. Isso força estruturalmente o fluxo em duas etapas — `inspect` (lista candidatos de fronteira com preview) e `convert` (só roda depois que assistente+humano decidiram os offsets, a voz e o idioma de destino) — nada de corte automático sem confirmação humana, e nenhuma configuração "esquecida" num `.env`.

Substituições específicas de um único livro (ex.: `texto.replace("ISBN 85-323-0309-", ...)` do notebook do Bandler, filtro de cabeçalho do PDF da Accenture) **não** são portadas para `src/` — são lixo por-livro, não lógica reutilizável.

**Sobre `.env`**: não existe mais `config.py` lendo configuração operacional de `.env`. Se sobrar algum uso legítimo de `.env` (ex.: uma chave de API de um backend de TTS pago, opcional, no futuro), ele é lido só onde for usado, via `os.getenv`, sem um módulo de config genérico — YAGNI enquanto não existir essa necessidade real.

## Skill Claude Code

`.claude/skills/book-to-audiobook/SKILL.md`, seguindo a convenção já vendorizada em [`.claude/skills/writing-skills/SKILL.md`](.claude/skills/writing-skills/SKILL.md) deste repo (skills são documentação de processo testada por pressão, não replicam lógica determinística — essa fica em `src/`, chamada via `Bash`).

### Como isso instala/compartilha de verdade (confirmado na doc oficial de Skills do Claude Code)

Isso responde diretamente a pergunta "como a pessoa instala se o código está na raiz do repositório": pela documentação oficial (`code.claude.com/docs/en/skills`, seção "Where skills live"), um **project skill** em `.claude/skills/<nome>/SKILL.md` tem escopo "this project only" e **carrega automaticamente quando o Claude Code é aberto dentro do repositório** — não existe passo de instalação separado. O fluxo real de distribuição é:

1. Usuário faz `git clone` do repositório público.
2. Abre o Claude Code dentro da pasta clonada.
3. `.claude/skills/book-to-audiobook/SKILL.md` já está disponível — o assistente descobre sozinho (via `description`) ou o usuário digita `/book-to-audiobook`.
4. O `src/` referenciado pelo `SKILL.md` (via `python -m src.cli ...`) funciona porque o comando roda com a raiz do repo como diretório de trabalho — não precisa empacotamento especial.

Ou seja: **o repositório inteiro já é a unidade de distribuição**, igual ao padrão usado no seu próprio [`pitch-video-studio`](https://github.com/gomesfellipe/pitch-video-studio) (repo privado do usuário, mesma estrutura: `.claude/skills/` + código de suporte na raiz do repo, README explicando "clone/baixe, abra o Claude Code na pasta, peça pra instalar"). Vale reaproveitar esse mesmo texto de instalação no README novo — inclusive o padrão de "primeira execução mais demorada" (a skill confere/instala dependências sozinha na primeira vez via `doctor`, e avisa que não é travamento).

**Também vamos empacotar como plugin** (confirmado com o usuário — entra no v1, não fica pra depois): basta criar `.claude/skills/book-to-audiobook/.claude-plugin/plugin.json`. Pela doc oficial (`plugins-reference`), qualquer pasta dentro de um diretório de skills que contenha esse manifesto carrega automaticamente como plugin `book-to-audiobook@skills-dir` — **sem marketplace, sem passo de instalação**, e o único campo obrigatório é `name`:

```json
{
  "name": "book-to-audiobook",
  "displayName": "Book to Audiobook",
  "description": "Converte epub/pdf em audiobook narrado (opcionalmente traduzido pra pt-BR), 100% gratuito e sem chave de API (edge-tts e GoogleTranslator são serviços gratuitos, mas online — precisa de internet).",
  "version": "0.1.0",
  "license": "MIT",
  "repository": "https://github.com/gomesfellipe/book-to-audiobook"
}
```

Isso dá duas formas de uso, sem trabalho extra de empacotamento: (a) clonar o repo inteiro (uso principal), ou (b) copiar só a pasta `.claude/skills/book-to-audiobook/` pra dentro do `.claude/skills/` de outro projeto Claude Code já existente — igual ao que o próprio `pitch-video-studio` oferece. Ressalva da doc que vale documentar no README: um plugin `@skills-dir` de escopo projeto só carrega a partir do diretório onde o Claude Code foi aberto (não sobe até a raiz do repo sozinho) — então instruir sempre "abra o Claude Code na raiz do repositório clonado".

Conteúdo: frontmatter com `description` cobrindo triggers tipo "transforme este epub em audiobook". Passos organizados como **gates** (mesmo padrão já validado no seu [`pitch-video-studio`](https://github.com/gomesfellipe/pitch-video-studio): a skill para em pontos específicos e espera confirmação explícita do usuário, nunca avança sozinha em etapas caras ou difíceis de desfazer):

| Gate | O que acontece |
| --- | --- |
| **0 — Setup** | `doctor` checa `ffmpeg` e libs Python; se faltar algo, a skill instala/orienta sozinha (1ª vez pode demorar, avisa que não é travamento) |
| **1 — Você manda o livro e as preferências** | Você fala o **nome do livro** (não precisa saber o caminho completo) — a skill procura o arquivo dentro da pasta `books/private/` (que já fica criada e pronta no repo, você só arrasta o epub/pdf pra lá antes); no chat, também diz idioma de destino (ou "sem tradução") e voz — nada disso vem de `.env`, é perguntado a cada acionamento |
| **2 — Inspeção** | `inspect --json` extrai texto + metadados (título/autor/subtítulo) + lista de `BoundaryCandidate` |
| **3 — Você aprova o corte de início/fim** | A skill mostra o preview de cada candidato e **espera confirmação explícita** antes de qualquer áudio — barra a racionalização "os marcadores do Gutenberg são óbvios, posso pular"; esse julgamento é o valor central da skill |
| **4 — Você confirma título/autor/subtítulo** | Usados para montar a intro falada ("Alice no País das Maravilhas, de Lewis Carroll.") |
| **5 — Você revisa a pronúncia** | Antes de sintetizar, a skill mostra o texto final (ou os trechos sinalizados — números, siglas, nomes próprios estrangeiros) para o usuário corrigir grafias que o TTS pronunciaria errado. Mesmo padrão do `pitch-video-studio`: corrigir pronúncia é revisão de **texto**, não um dicionário fonético — mais simples e mais leve |
| **6 — Convert** | Só depois dos gates acima: `convert` (com `--start-char`/`--end-char`/`--voice`/`--translate-to` já decididos) gera a intro falada + o áudio do conteúdo, concatenados |
| **7 — Você confere o resultado** | Checar duração/tamanho do mp3 final, ouvir e reportar |

Seção "common mistakes": confundir sumário com início real, pular o gate de pronúncia, gerar `convert` sem ter mostrado o preview ao usuário, ler configuração de um `.env` em vez de perguntar no chat.

## Reestruturação do repositório

1. **`examples/*.ipynb`** (~14 arquivos): apagar todos — lógica genérica já extraída para `src/loaders/` no passo anterior.
2. **`blog_post/`**: remover do repo público (motivo licença CC BY-NC-ND + uso de fairmlbook, ver diagnóstico acima).
3. **`main.ipynb`**: remover — era o padrão manual que originou o problema; README passa a ser a interface de quickstart via CLI/skill.
4. **Pasta de input privada**: criar `books/private/.gitkeep` + `books/private/README.md` explicando que livros pessoais nunca são versionados; `.gitignore` ganha `books/private/*` (exceto `.gitkeep`). É só uma convenção de pasta — não é referenciada por nenhum `.env`, o usuário aponta o caminho do arquivo na conversa com o assistente.
5. **Fixture de demo**: o usuário mesmo baixa o epub de *Alice's Adventures in Wonderland* (domínio público, Project Gutenberg) e coloca em `tests/fixtures/` quando o assistente pedir nesse ponto do fluxo (não é o agente que baixa sozinho da internet) — usado nos testes e no quickstart do README.
6. **Atualizar**: `.env.example` (esvaziar — remover `BOOKS_PATH`/`OUTPUT_PATH`/`TTS_*`/`TRANSLATE_*`; deixar só um comentário indicando que nenhuma chave é necessária hoje e o arquivo fica reservado pra um backend pago futuro), `README.md` (quickstart real: pré-requisitos incluindo `ffmpeg`, `pip install -r requirements.txt`, exemplo com o fixture, deixar claro que voz/idioma/arquivo são perguntados pelo assistente na hora, não configurados em arquivo), `requirements.txt` (remover `PyPDF2`, manter `PyMuPDF`, adicionar `requirements-dev.txt` com `pytest`).
7. **Reiniciar histórico do git** (etapa própria, destrutiva, confirmar antes de executar):
   ```bash
   git branch legacy-full-history main   # backup local, nunca pushado
   git checkout --orphan clean-main
   git add <arquivos decididos nos passos 1-6>
   git commit -m "Initial public commit: book-to-audiobook skill"
   git branch -m main legacy-local
   git branch -m clean-main main
   # git push --force-with-lease origin main   -- só com confirmação explícita no momento
   ```

## Sequência de prompts recomendada

Cada bloco abaixo é um prompt **pronto pra copiar e colar**, um por vez, em ordem. Foram escritos para funcionar mesmo **num chat novo, do zero** (você disse que ia abrir sessões separadas) — por isso todos começam pedindo pra ler o plano inteiro antes de agir, e todos citam o caminho completo do arquivo. Não pule a ordem: os destrutivos (9 e 10) são isolados de propósito, e não devem ser colados junto com nenhum outro passo.

Antes do Prompt 1, copie este arquivo de plano pra dentro do repositório (assim ele sobrevive além da pasta `~/.claude/plans/`, que é temporária):

```bash
mkdir -p docs && cp /Users/fellipegomes/.claude/plans/ta-vendo-esse-link-twinkly-aurora.md docs/modernization-plan.md
```

A partir daqui, todo prompt referencia `docs/modernization-plan.md` (relativo à raiz do repo) em vez do caminho em `~/.claude/plans/`.

---

**Prompt 1 — Auditoria do legado**

```text
Estou no repositório book-to-audiobook. Leia o arquivo docs/modernization-plan.md
por completo antes de fazer qualquer coisa — ele é o plano de modernização deste
repo legado (pipeline manual de livro -> audiobook em pt-BR) para virar uma
Claude Code Skill pública.

Invoque o skill `improve` para auditar o estado ATUAL do repositório (src/,
main.ipynb, examples/, blog_post/) como um projeto legado que vai ser
transformado conforme esse plano. Quero uma segunda opinião só-leitura sobre
dívida técnica, riscos de copyright e gaps de arquitetura, pra cruzar com o
plano antes de começar a implementar. Não implemente nada ainda, só relatório.
```

---

**Prompt 2 — Brainstorming da arquitetura**

```text
Leia docs/modernization-plan.md por completo (plano de modernização do
book-to-audiobook). Invoque o skill `brainstorming` trazendo esse plano como
ponto de partida para fechar detalhes em aberto antes de formalizar tarefas:
formato exato da saída JSON do comando `inspect`, nomes de módulos em src/,
qualquer ponto do plano que pareça ambíguo ou incompleto. Não escreva código
ainda, só decisões de design.
```

---

**Prompt 3 — Plano formal de tarefas**

```text
Leia docs/modernization-plan.md. Com base nele (e no brainstorming da sessão
anterior, se você tiver as notas — senão refaça as decisões principais a
partir do próprio plano), invoque o skill `writing-plans` para transformar
isso num plano de tarefas testáveis, com critério de aceite por módulo:
src/loaders/ (epub, pdf, txt), boundary.py, metadata.py, intro.py,
pronunciation.py, translate.py, text_to_speech.py, tools.py, pipeline.py,
cli.py, SKILL.md, plugin.json.
```

---

**Prompt 4 — Isolar workspace**

```text
Leia docs/modernization-plan.md. Antes de tocar em qualquer código, crie um
branch de feature isolado do main atual (use o skill using-git-worktrees se
fizer sentido) — o main ainda tem os notebooks de examples/ com texto de
livros comerciais, não mexa nisso agora. Sugestão de nome: modernize-skill.
Confirme comigo o nome do branch antes de criar.
```

---

**Prompt 5 — TDD dos loaders**

```text
Leia docs/modernization-plan.md, seção "Arquitetura nova de src/". Usando o
skill test-driven-development, implemente src/loaders/ (epub_loader.py,
pdf_loader.py, txt_loader.py) e o dispatch load_book(). Escreva os testes
primeiro. Nesta etapa eu vou te fornecer o arquivo
tests/fixtures/alice.epub (baixado por mim do Project Gutenberg) — me avise
exatamente quando precisar dele e onde devo colocá-lo antes de continuar.
```

---

**Prompt 6 — TDD de boundary/metadata/intro/pronunciation/translate**

```text
Leia docs/modernization-plan.md, seção "Arquitetura nova de src/". Usando
test-driven-development, implemente boundary.py, metadata.py, intro.py,
pronunciation.py, e corrija translate.py (source/target como parâmetros
explícitos, sem default de .env). Teste boundary.py com textos sintéticos
contendo marcadores do Gutenberg E casos sem marcador nenhum (a detecção não
pode depender só dos marcadores — isso está explicado no plano). Nenhum texto
de livro comercial em nenhum teste.
```

---

**Prompt 7 — TDD de pipeline/cli**

```text
Leia docs/modernization-plan.md. Usando test-driven-development, implemente
pipeline.py (convert_book_to_audio) e cli.py com os subcomandos doctor,
inspect e convert, exatamente como descrito na seção "Arquitetura nova de
src/". Corrija também text_to_speech.py (erro explícito se output_file já
existir, em vez do print+return silencioso atual).
```

---

**Prompt 8 — Revisão e verificação**

```text
Leia docs/modernization-plan.md, seção "Verificação". Invoque
requesting-code-review sobre todo o código novo em src/ e tests/, aplique as
correções que fizerem sentido, depois invoque verification-before-completion.
Rode a suíte pytest completa e me mostre o resultado antes de seguirmos —
não avance pro próximo prompt sem tudo verde.
```

---

**Prompt 9 — Limpeza do repositório (DESTRUTIVO — leia com atenção antes de rodar)**

```text
Leia docs/modernization-plan.md, seções "Reestruturação do repositório"
(itens 1-6, SEM o item 7 de git) e "Decisões já validadas". Esta é uma etapa
destrutiva: apagar examples/*.ipynb, remover blog_post/ e main.ipynb, criar
books/private/, atualizar .gitignore/.env.example/README.md/requirements.txt.

ANTES de rodar qualquer `git rm` ou `rm`, liste pra mim exatamente cada
arquivo/pasta que vai apagar ou mover, e espere minha confirmação explícita
no chat. Não prossiga sem esse "sim" meu.
```

---

**Prompt 10 — Reiniciar histórico do git (DESTRUTIVO — isolado, só depois do Prompt 9 confirmado)**

```text
Leia docs/modernization-plan.md, seção "Reestruturação do repositório", item
7. Reinicie o histórico do git exatamente como descrito: branch de backup
local legacy-full-history, git checkout --orphan, commit único limpo,
renomear branches (main vira legacy-local, clean-main vira main).

NÃO rode `git push --force-with-lease` em hipótese nenhuma nesta etapa,
mesmo que eu já tenha confirmado os passos anteriores — isso reescreve o
histórico do remoto e precisa de uma confirmação minha separada, feita
depois que eu conferir localmente que git log --oneline mostra só 1 commit e
git ls-files está correto.
```

---

**Prompt 11 — Empacotar a Skill**

```text
Leia docs/modernization-plan.md, seções "Skill Claude Code" (incluindo a
tabela de Gates) e "Como isso instala/compartilha de verdade". Invoque
writing-skills para criar .claude/skills/book-to-audiobook/SKILL.md e
.claude/skills/book-to-audiobook/.claude-plugin/plugin.json (use o JSON de
exemplo do plano). Siga o ciclo RED-GREEN-REFACTOR: teste com um subagente
simulando um usuário real se ele pula o Gate 3 (confirmação de corte) ou o
Gate 5 (revisão de pronúncia) sem a skill presente, documente a
racionalização que ele usa, e feche essa lacuna no texto da skill.
```

---

**Prompt 12 — Teste end-to-end real**

```text
Vou colocar agora o arquivo tests/fixtures/alice.epub (baixei do Project
Gutenberg). Depois que eu confirmar que está lá: rode o teste end-to-end
como se você fosse um usuário real pedindo "transforme
tests/fixtures/alice.epub em audiobook em português". Siga todos os Gates do
SKILL.md (docs/modernization-plan.md tem a tabela completa) e me avise em
cada Gate antes de avançar pro próximo, até gerar o mp3 final.
```

---

**Prompt 13 — Finalizar o branch**

```text
Leia docs/modernization-plan.md, seção "Verificação". Rode a checklist
completa: git log --oneline (deve mostrar 1 commit no main novo), git
ls-files (não deve ter examples/ nem blog_post/), du -sh .git (deve estar
bem menor que os ~5,6 MB originais), grep por texto de livro comercial fora
de tests/fixtures/. Me mostre os resultados de cada checagem. Só depois
disso invoque finishing-a-development-branch para decidirmos sobre o merge
e, com minha confirmação explícita separada, o primeiro `git push` público.
```

## Verificação

- **Unitários** (`pytest`): loaders (epub via fixture pequena, pdf/txt sintéticos), `boundary.py` (candidatos + trim, caso Gutenberg exato e casos sem marcador nenhum), `metadata.py`/`intro.py` (extração de título/autor/subtítulo + texto de intro), `pronunciation.py` (sinaliza siglas/números/nomes estrangeiros sem alterar o texto), `tools.py` (corte sem quebrar palavra, concatenação de mp3s), `translate.py` (mock de `GoogleTranslator.translate`, confirmar que `source`/`target` são parâmetros obrigatórios, sem default mágico), `cli.py` (`doctor` detecta `ffmpeg` ausente via mock). Suíte inteira roda rápido em 8GB RAM, sem dependência de modelo de ML.
- **End-to-end manual** (não obrigatório em CI, precisa de rede e `edge-tts` instalado): pipeline completo com o fixture de *Alice's Adventures in Wonderland*, incluindo a intro falada gerada a partir do título/autor.
- **Checagem de copyright antes do primeiro push público**:
  - `git log --oneline` no novo `main` mostra exatamente 1 commit.
  - `git ls-files` não contém `examples/` nem `blog_post/`.
  - `du -sh .git` do repo novo é drasticamente menor que o atual (~5,6 MB hoje).
  - Nenhum trecho de texto de livro comercial em arquivos versionados fora de `tests/fixtures/*.epub` (domínio público).
  - `legacy-local`/tag de backup não estão entre os refs enviados no `git push`.
- **Checagem de configuração**: `.env.example` não contém nenhuma variável operacional (voz, idioma, caminhos) — só comentário sobre chaves de API futuras opcionais; `grep -r "os.getenv\|dotenv"` em `src/` não deve aparecer fora de um eventual uso pontual de chave de API.
- **README**: seguir o quickstart do zero (clone/worktree limpo) confirmando que funciona sem contexto extra, incluindo checagem de `ffmpeg`.
