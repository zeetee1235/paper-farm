# paper-farm

Zotero → LLM summarization → Obsidian. Watches your Zotero storage, runs each new PDF through a text extraction and summarization pipeline, and writes a structured Markdown note into your Obsidian vault.

```
Zotero storage  →  paper-farm watch  →  Obsidian vault/
                                          <paper-id>/
                                            summary.md
                                            metadata.json
                                            notes.md
                                            paper.pdf
```

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally (`ollama serve`)
- A pulled model, e.g. `ollama pull phi4:14b`
- *(Optional)* Rust toolchain — only needed for DocStruct OCR on scanned PDFs

---

## Install

```bash
git clone --recurse-submodules <repo-url>
cd paper-farm-lab

# with uv (recommended)
uv sync

# or pip
pip install -e .
```

---

## Configure

```bash
paper-farm init-config        # creates paper-farm.toml
```

Edit the generated file:

```toml
[paths]
obsidian_vault = "~/Documents/Obsidian/Research/papers"

[llm]
backend  = "ollama"
model    = "phi4:14b"
timeout  = 600

[summary]
language = "en"   # en / ko / ja / zh / fr / de / es

[watcher]
zotero_storage = "~/Zotero/storage"
poll_interval  = 30
```

---

## Usage

### Automatic (recommended)

Watch Zotero and process new papers as they arrive:

```bash
paper-farm watch
```

Or use the helper scripts:

```bash
scripts/start-watch.sh       # starts watcher + logs to logs/
scripts/monitor.sh           # live dashboard (queue, progress, recent logs)
```

### Manual (single paper)

```bash
# Full pipeline in one command
paper-farm run /path/to/paper.pdf

# Step by step
paper-farm ingest /path/to/paper.pdf --title "..." --authors "A, B" --year 2024
paper-farm parse   <paper-id>
paper-farm summarize <paper-id>
paper-farm export  <paper-id>
```

### Inspect

```bash
paper-farm list               # all registered papers
paper-farm show <paper-id>    # metadata + artifact status
```

---

## Output (per paper in Obsidian)

| File | Contents |
|------|----------|
| `summary.md` | LLM-generated structured summary with YAML front-matter |
| `metadata.json` | Title, authors, year, venue, DOI, tags |
| `notes.md` | Blank note template (Research Ideas / Questions / Follow-up Papers) |
| `paper.pdf` | Copy of the original PDF |

---

## Extraction

paper-farm uses a two-stage extraction strategy to avoid slow OCR on text-based PDFs:

1. **pypdf** — extracts text directly (~1 s/paper). Used when the quality score ≥ 60/100.
2. **DocStruct OCR** — full OCR via Tesseract (~2–10 min/paper). Used only for scanned PDFs.

Quality is scored across five signals: characters/page, non-whitespace ratio, printable-character ratio, academic keyword presence, and per-page yield.

### Build DocStruct (optional, for scanned PDFs)

```bash
git submodule update --init --recursive
cargo build --release --manifest-path external/DocStruct/Cargo.toml
pip install "Pillow>=11,<12" pytesseract pdf2image "opencv-python>=4.8,<5" numpy
```

---

## Project layout

```
src/paper_farm/
  cli.py            CLI entry point
  config.py         Settings (loaded from paper-farm.toml)
  pipeline/         Orchestration service
  extractors/       pypdf + DocStruct OCR + SmartExtractor
  normalizers/      Text cleaning and section detection
  summarizers/      Ollama and rule-based backends
  exporters/        Obsidian Markdown writer
  watchers/         Zotero file watcher (queue-based)
  storage/          File-backed repository
data/               Pipeline cache (excluded from git — see .gitignore)
scripts/            Shell helpers (start-watch, monitor, sync)
external/DocStruct  OCR submodule (Rust)
```

---

## Development

```bash
uv sync
uv run pytest
```
