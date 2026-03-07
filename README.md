# paper-farm (MVP)

`paper-farm` is a **local-first MVP** for ingesting one research paper PDF at a time and generating structured outputs that are easy to inspect and extend.

## MVP scope

This project currently focuses on a practical single-paper pipeline:

1. Register PDF and metadata
2. Extract text
3. Normalize/clean text + detect sections
4. Summarize in either:
   - `local` mode (deterministic heuristic summary)
   - `agent-pr` mode (agent-ready package generation)
5. Export an Obsidian-friendly Markdown note (for local summaries)

It is intentionally lean: no web frontend, no queueing layer, and no vector DB.

## Requirements

- Python 3.11+

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run end-to-end

```bash
paper-farm run /path/to/paper.pdf --summary-mode local
```

### Stage-by-stage commands

```bash
paper-farm ingest <pdf_path>
paper-farm extract <paper_id>
paper-farm normalize <paper_id>
paper-farm summarize <paper_id> --mode local
paper-farm summarize <paper_id> --mode agent-pr
paper-farm export <paper_id> --source local
paper-farm list
paper-farm show <paper_id>
```

## Data layout

```text
data/
  papers/
    <paper_id>/
      original.pdf
      metadata.json
      extracted.json
      cleaned.json
      summary.local.json
      note.local.md
      agent_package/
        prompt.txt
        summary_request.json
        output_contract.json
```

## Project structure

```text
src/paper_farm/
  cli.py
  config.py
  logging.py
  models/
  storage/
  pipeline/
  extractors/
  normalizers/
  summarizers/
  exporters/
  utils/
tests/
```

## Current limitations

- PDF extraction is best-effort fallback-oriented for MVP.
- Local summarization is deterministic heuristics, not an LLM.
- `agent-pr` mode only prepares a package; it does not call external agents.
- Metadata enrichment (authors/year/source parsing) is minimal.

## Extension points

- Replace `SimpleTextExtractor` with a full DocStruct extractor.
- Add a real local LLM backend behind the summary interface.
- Add an agent execution workflow that consumes `agent_package/` and produces PR-ready artifacts.

## Next steps

1. **Real DocStruct integration**
   - Implement a production `DocStructExtractor` that returns rich structural blocks (title/authors/sections/tables/references) and register it as a selectable extractor backend.
   - Preserve both raw DocStruct output and mapped `extracted.json` for debugging.

2. **Real local LLM integration**
   - Add a model-backed summary backend (e.g., llama.cpp/Ollama) behind the existing summary interface.
   - Keep the current summary schema unchanged, and add prompt/version metadata to `summary.local.json` for reproducibility.

3. **Git-based agent PR automation**
   - Add a command that consumes `agent_package/`, runs an external coding/research agent, writes returned artifacts, and optionally opens a git commit + PR draft.
   - Keep this opt-in and transparent (dry-run + explicit target branch/repo options).
