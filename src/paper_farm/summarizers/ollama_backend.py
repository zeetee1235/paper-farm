"""Ollama HTTP API summarizer backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from paper_farm.models.artifacts import PaperStruct, SummaryResult


def _build_system_prompt(language_name: str) -> str:
    return f"""\
You are a research assistant. Read the paper content and return a JSON object with exactly these fields:
- summary: one paragraph summary in {language_name}
- contributions: list of 3 main contributions (strings, {language_name})
- method: description of methods/approach ({language_name})
- results: key results and metrics ({language_name})
- limitations: limitations or future work ({language_name})
- keywords: list of 5-8 English keywords (always in English regardless of language setting)

Rules:
- Answer only with a valid JSON object, no markdown fences, no extra text
- Keywords are always in English
- If information is unclear, write "unclear" for that field
- Do not hallucinate details not in the paper
"""


class OllamaSummaryBackend:
    """Summarizes papers using a locally running Ollama model."""

    def __init__(
        self,
        model: str = "llama3:8b",
        base_url: str = "http://localhost:11434",
        timeout: int = 300,
        language_name: str = "English",
        section_char_limit: int = 2000,
        total_char_limit: int = 16000,
    ):
        self.model              = model
        self.base_url           = base_url.rstrip("/")
        self.timeout            = timeout
        self.language_name      = language_name
        self.section_char_limit = section_char_limit
        self.total_char_limit   = total_char_limit

    def summarize(self, paper: PaperStruct) -> SummaryResult:
        user_content = self._build_user_content(paper)
        raw = self._call_ollama(user_content)
        parsed = self._parse_response(raw)
        obsidian_markdown = self._build_markdown(paper.title, parsed)
        return SummaryResult(
            title=paper.title,
            summary=parsed.get("summary", ""),
            contributions=parsed.get("contributions", []),
            method=parsed.get("method", ""),
            results=parsed.get("results", ""),
            limitations=parsed.get("limitations", ""),
            keywords=parsed.get("keywords", []),
            obsidian_markdown=obsidian_markdown,
        )

    def _build_user_content(self, paper: PaperStruct) -> str:
        parts = [f"Title: {paper.title}"]
        if paper.abstract:
            parts.append(f"\nAbstract:\n{paper.abstract}")
        for section in paper.sections:
            content = section.content[:self.section_char_limit]
            parts.append(f"\n## {section.name}\n{content}")
        return "\n".join(parts)[:self.total_char_limit]

    def _call_ollama(self, user_content: str) -> str:
        system_prompt = _build_system_prompt(self.language_name)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            "stream": False,
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
                return data["message"]["content"]
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama 연결 실패 ({self.base_url}). "
                "ollama가 실행 중인지 확인하세요: `ollama serve`"
            ) from exc

    def _parse_response(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "summary": raw[:500],
                "contributions": [],
                "method": "",
                "results": "",
                "limitations": "",
                "keywords": [],
            }

    @staticmethod
    def _build_markdown(title: str, d: dict) -> str:
        contributions = "\n".join(f"- {c}" for c in d.get("contributions", []))
        keywords = ", ".join(d.get("keywords", []))
        return (
            f"# {title}\n\n"
            "## Summary\n"
            f"{d.get('summary', '')}\n\n"
            "## Contributions\n"
            f"{contributions}\n\n"
            "## Method\n"
            f"{d.get('method', '')}\n\n"
            "## Results\n"
            f"{d.get('results', '')}\n\n"
            "## Limitations\n"
            f"{d.get('limitations', '')}\n\n"
            "## Keywords\n"
            f"{keywords}\n"
        )
