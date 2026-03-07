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

