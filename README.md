<img src="docs/logo.png" alt="paper-farm" width="160" align="left" style="margin-right:24px; margin-bottom:4px;" />

# paper-farm

A local-first pipeline that monitors your Zotero storage for new research PDFs, extracts and normalizes the full text, generates a structured LLM summary, and writes the result as a Markdown note into your Obsidian vault — automatically, with no manual steps required.

한국어 문서: [README.ko.md](./README.ko.md)

<br clear="left" />

---

## Overview

<p align="center">
  <img src="docs/pipeline.svg" alt="paper-farm pipeline" width="870"/>
</p>

> **Figure 1.** End-to-end processing pipeline. A queue-based watcher thread detects new PDFs in Zotero storage; each paper is then extracted, normalized, summarized by a local LLM, and exported as a structured Obsidian note. Stages run sequentially per paper to bound memory usage.

Each paper produces a self-contained directory in the Obsidian vault:

```
<obsidian-vault>/
  <paper-id>/
    summary.md      ← LLM-generated structured summary (YAML front-matter)
    metadata.json   ← title, authors, year, venue, DOI, tags
    notes.md        ← blank template (Research Ideas / Questions / Follow-up)
    paper.pdf       ← copy of the source PDF
```

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally — `ollama serve`
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
paper-farm init-config        # writes paper-farm.toml in the current directory
```

Edit the generated file:

```toml
[paths]
obsidian_vault = "~/Documents/Obsidian/Research/papers"

[llm]
backend  = "ollama"
model    = "phi4:14b"         # run: ollama pull phi4:14b
timeout  = 600                # seconds; 600 recommended for 14B models

[summary]
language = "en"               # en / ko / ja / zh / fr / de / es

[watcher]
zotero_storage = "~/Zotero/storage"
poll_interval  = 30           # seconds between scans
```

> **Zotero storage path**
> macOS / Windows: `~/Zotero/storage` · Linux (snap): `~/snap/zotero-snap/common/Zotero/storage`

---

## Usage

### Automatic mode (recommended)

Watch Zotero and process new papers as they arrive:

```bash
paper-farm watch
```

Or use the provided shell helpers:

```bash
scripts/start-watch.sh       # launches watcher and writes logs to logs/
scripts/monitor.sh           # live dashboard — queue status, progress, recent logs
```

### Manual mode

```bash
# Full pipeline in one command
paper-farm run /path/to/paper.pdf --title "Attention Is All You Need" \
    --authors "Vaswani, Shazeer" --year 2017

# Stage-by-stage
paper-farm ingest    /path/to/paper.pdf
paper-farm parse     <paper-id>
paper-farm summarize <paper-id>
paper-farm export    <paper-id>
```

### Inspection

```bash
paper-farm list               # all registered papers
paper-farm show <paper-id>    # metadata + artifact status per stage
```

---

## Smart Extraction

<p align="center">
  <img src="docs/extraction.svg" alt="Smart extraction flow" width="500"/>
</p>

> **Figure 2.** Two-stage extraction strategy. pypdf is attempted first; a five-signal quality scorer (maximum 100 pts) determines whether the extracted text is sufficient. If the score falls below the threshold of 60, the paper is re-processed using DocStruct OCR — a Rust/Tesseract pipeline that handles scanned documents at the cost of significantly higher latency.

| Signal | Weight | Description |
|--------|--------|-------------|
| chars / page | 30 pts | Raw character count relative to page count |
| non-whitespace ratio | 20 pts | Fraction of non-whitespace characters |
| printable-char ratio | 20 pts | Fraction of ASCII-printable characters; OCR noise scores low |
| academic keyword hits | 20 pts | Presence of headings: *abstract, introduction, references, …* |
| page yield | 10 pts | Fraction of pages returning non-empty text |

### Build DocStruct (optional — scanned PDFs only)

```bash
git submodule update --init --recursive
cargo build --release --manifest-path external/DocStruct/Cargo.toml
pip install "Pillow>=11,<12" pytesseract pdf2image "opencv-python>=4.8,<5" numpy
```

If the binary is absent, paper-farm falls back to pypdf automatically.

---

## Project layout

```
src/paper_farm/
  cli.py            CLI entry point (Typer)
  config.py         Settings — loaded from paper-farm.toml
  pipeline/         PipelineService: ingest → parse → summarize → export
  extractors/       SmartExtractor, SimpleTextExtractor, DocStructExtractor
  normalizers/      Text cleaning and section boundary detection
  summarizers/      OllamaSummaryBackend, LocalSummaryBackend (rule-based)
  exporters/        Obsidian Markdown + metadata.json writer
  watchers/         ZoteroWatcher — scanner thread + worker queue
  storage/          File-backed repository (data/)
data/               Pipeline cache — excluded from git (see .gitignore)
scripts/            Shell helpers: start-watch.sh, monitor.sh, sync.sh
external/DocStruct  OCR submodule (Rust + Tesseract)
```

---

## Development

```bash
uv sync
uv run pytest
```
