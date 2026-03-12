"""Ollama HTTP API summarizer backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from paper_farm.models.artifacts import PaperStruct, SummaryResult

# Sections that add no value for summarization
_SKIP_SECTIONS = frozenset({
    "references", "acknowledgment", "acknowledgments", "appendix",
})

# Threshold: sections longer than this get map-extracted before the reduce pass
_MAP_THRESHOLD = 2000


def _build_system_prompt(language_name: str) -> str:
    return f"""\
You are a research paper analysis assistant. Read the extracted paper content and return a single JSON object with exactly the fields listed below.

Output language: {language_name} — except where noted.

Fields:
- summary: one-sentence summary of the paper's core contribution ({language_name})
- problem: the problem this paper addresses ({language_name})
- key_idea: the core idea or approach ({language_name})
- method: methods, models, or algorithms used ({language_name})
- experiment: JSON object with keys "dataset", "simulator", "metric" ({language_name})
- results: key results and metrics ({language_name})
- contributions: list of exactly 3 contribution strings ({language_name})
- limitations: limitations acknowledged by the paper ({language_name})
- future_work: future directions suggested by the paper ({language_name})
- keywords: list of 5–8 keywords (always in English)

Hard rules — follow without exception:
1. Return only a valid JSON object. No markdown fences, no prose outside the object.
2. Technical terms, acronyms, protocol names, and algorithm names must stay in English even when the surrounding text is in {language_name}.
   Examples: RPL, DIO, DAO, DIS, DODAG, IoT, 6LoWPAN, trust, rank, TSCH, MQTT, IDS, ML, CNN, LSTM, GAN — never transliterate these.
3. keywords must always be in English.
4. If information is absent or unclear, use "N/A".
5. Do not invent details not present in the paper.
"""


def _build_map_prompt(section_name: str) -> str:
    return (
        f"Extract the key information from this '{section_name}' section of a research paper.\n"
        "Be concise (100–150 words). Cover: core contribution or finding, method or approach used, "
        "quantitative results if present, and any limitations mentioned.\n"
        "Write plain prose, no JSON, no bullet points.\n\n"
    )


class OllamaSummaryBackend:
    """Summarizes papers using a locally running Ollama model.

    Uses a map-reduce strategy:
    - MAP:    sections longer than _MAP_THRESHOLD chars are condensed to ~150 words each
              via a focused LLM call before the reduce pass.
    - REDUCE: all (possibly condensed) section texts are assembled and sent in a
              single structured JSON extraction call.
    """

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

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def summarize(self, paper: PaperStruct) -> SummaryResult:
        user_content = self._build_reduce_input(paper)
        raw = self._call_ollama(
            system=_build_system_prompt(self.language_name),
            user=user_content,
        )
        parsed = self._parse_response(raw)
        obsidian_markdown = self._build_markdown(paper.title, parsed)
        experiment_raw = parsed.get("experiment", {})
        if isinstance(experiment_raw, dict):
            experiment_str = "\n".join(
                f"- **{k.capitalize()}**: {v}" for k, v in experiment_raw.items()
            )
        else:
            experiment_str = str(experiment_raw)
        return SummaryResult(
            title=paper.title,
            summary=parsed.get("summary", ""),
            problem=parsed.get("problem", ""),
            key_idea=parsed.get("key_idea", ""),
            method=parsed.get("method", ""),
            experiment=experiment_str,
            results=parsed.get("results", ""),
            contributions=parsed.get("contributions", []),
            limitations=parsed.get("limitations", ""),
            future_work=parsed.get("future_work", ""),
            keywords=parsed.get("keywords", []),
            obsidian_markdown=obsidian_markdown,
        )

    # ------------------------------------------------------------------
    # Map-reduce helpers
    # ------------------------------------------------------------------

    def _build_reduce_input(self, paper: PaperStruct) -> str:
        """Build the user message for the reduce (final JSON) call.

        Long sections are condensed via a map call first; short ones are
        included verbatim. The result is capped at total_char_limit so the
        reduce call stays within context budget.
        """
        parts = [f"Title: {paper.title}"]
        for section in paper.sections:
            name_lower = section.name.lower()
            if name_lower in _SKIP_SECTIONS:
                continue
            content = section.content
            if len(content) > _MAP_THRESHOLD:
                content = self._map_section(section.name, content)
            parts.append(f"\n## {section.name}\n{content}")
        return "\n".join(parts)[:self.total_char_limit]

    def _map_section(self, section_name: str, content: str) -> str:
        """Condense a long section to ~150 words using a focused LLM call."""
        prompt = _build_map_prompt(section_name) + content[:self.section_char_limit * 4]
        try:
            return self._call_ollama(system="You are a concise research assistant.", user=prompt)
        except Exception:
            # Fall back to simple truncation if map call fails
            return content[:self.section_char_limit]

    # ------------------------------------------------------------------
    # Ollama transport
    # ------------------------------------------------------------------

    def _call_ollama(self, *, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
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
        experiment_raw = d.get("experiment", {})
        if isinstance(experiment_raw, dict):
            non_na = {k: v for k, v in experiment_raw.items() if v and str(v).upper() != "N/A"}
            if non_na:
                experiment_lines = "\n".join(f"- **{k.capitalize()}**: {v}" for k, v in non_na.items())
            else:
                experiment_lines = "N/A"
        else:
            experiment_lines = str(experiment_raw)
        return (
            f"# {title}\n\n"
            "## One-line Summary\n"
            f"{d.get('summary', '')}\n\n"
            "## Problem\n"
            f"{d.get('problem', '')}\n\n"
            "## Key Idea\n"
            f"{d.get('key_idea', '')}\n\n"
            "## Method\n"
            f"{d.get('method', '')}\n\n"
            "## Experiment\n"
            f"{experiment_lines}\n\n"
            "## Results\n"
            f"{d.get('results', '')}\n\n"
            "## Contributions\n"
            f"{contributions}\n\n"
            "## Limitations\n"
            f"{d.get('limitations', '')}\n\n"
            "## Future Work\n"
            f"{d.get('future_work', '')}\n\n"
            "## Keywords\n"
            f"{keywords}\n"
        )
