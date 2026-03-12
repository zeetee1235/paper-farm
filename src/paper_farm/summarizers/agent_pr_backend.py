"""Agent package generator backend."""

import json
from pathlib import Path

from paper_farm.models.artifacts import CleanedArtifact
from paper_farm.utils.jsonio import write_json


class AgentPRSummaryBackend:
    """Creates an agent-ready package without calling external systems."""

    mode = "agent-pr"

    def summarize(self, paper_id: str, cleaned: CleanedArtifact, paper_dir: Path) -> None:
        package_dir = paper_dir / "agent_package"
        package_dir.mkdir(parents=True, exist_ok=True)

        prompt = (
            "You are a research paper analysis assistant.\n"
            "Read the normalized paper content and produce two output files:\n"
            "1) summary.agent.json — a structured JSON matching every field in output_contract.json.\n"
            "2) note.agent.md — an Obsidian-ready Markdown note.\n\n"
            "Hard rules:\n"
            "- Technical terms, acronyms, protocol names, and algorithm names must stay in English "
            "regardless of the output language (e.g. RPL, DIO, DAO, DIS, DODAG, IoT, 6LoWPAN, "
            "trust, rank, TSCH, IDS, LSTM, GAN — never transliterate these).\n"
            "- keywords must always be in English.\n"
            "- Mark uncertain claims explicitly; do not fabricate details.\n"
            "- Return only the requested files; no extra commentary."
        )
        (package_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

        request = {
            "paper_id": paper_id,
            "mode": self.mode,
            "sections": cleaned.sections,
            "cleaned_text": cleaned.cleaned_text[:20000],
            "targets": {
                "summary_json": "summary.agent.json",
                "note_markdown": "note.agent.md",
            },
        }
        contract = {
            "required_summary_fields": [
                "mode",
                "one_line",
                "short_summary",
                "contributions",
                "methods",
                "experiments",
                "limitations",
                "keywords",
            ],
            "expected_files": ["summary.agent.json", "note.agent.md"],
            "notes": "mode should be `agent-pr` in summary.agent.json",
        }

        write_json(package_dir / "summary_request.json", request)
        write_json(package_dir / "output_contract.json", contract)
        self._write_agent_md(package_dir, prompt, request, contract)

    def _write_agent_md(self, package_dir: Path, prompt: str, request: dict, contract: dict) -> None:
        """Write a single-file handoff for external agents."""
        contract_json = json.dumps(contract, ensure_ascii=False, indent=2)
        request_json = json.dumps(request, ensure_ascii=False, indent=2)
        agent_md = f"""# Agent Handoff

Use this single file as the source of truth.

## Goal

Create two files in this directory:

- `summary.agent.json`
- `note.agent.md` (Obsidian-ready)

## Prompt

{prompt}

## Output Contract

```json
{contract_json}
```

## Request Payload

```json
{request_json}
```

## Required Output Files

1. `summary.agent.json`: Must include every field from `required_summary_fields`.
2. `note.agent.md`: Clean Markdown for Obsidian.

## Hard Rules

- Technical terms, acronyms, protocol names, and algorithm names must stay in English regardless of output language (e.g. RPL, DIO, DAO, DIS, DODAG, IoT, 6LoWPAN, trust, rank, TSCH, IDS, LSTM, GAN — never transliterate).
- `keywords` must always be in English.
- Mark uncertain claims explicitly. Do not fabricate details.
- Output only the two requested files; no extra commentary.
"""
        (package_dir / "agent.md").write_text(agent_md, encoding="utf-8")
