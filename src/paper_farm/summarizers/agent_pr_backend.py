"""Agent package generator backend."""

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
            "You are a research assistant agent. Read normalized paper content and produce:\n"
            "1) A structured JSON summary matching output_contract.json.\n"
            "2) A clean Obsidian-ready Markdown note.\n"
            "Be explicit about uncertain claims and avoid fabricated details."
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
