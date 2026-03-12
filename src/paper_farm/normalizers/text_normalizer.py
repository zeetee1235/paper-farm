"""Text normalization and section split for paper struct creation."""

import re

from paper_farm.models.artifacts import PaperSection, PaperStruct


class BasicTextNormalizer:
    """Deterministic normalizer that converts raw text into paper_struct."""

    HEADING_PATTERNS = [
        "Abstract",
        "Introduction",
        "Background",
        "Related Work",
        "Method",
        "Methods",
        "Approach",
        "Experiment",
        "Experiments",
        "Results",
        "Discussion",
        "Conclusion",
        "Limitations",
        "References",
    ]

    def to_paper_struct(self, title: str, raw_text: str) -> PaperStruct:
        cleaned = self._cleanup(raw_text)
        sections = self._split_sections(cleaned)
        abstract = sections.get("Abstract", "")[:2500]
        normalized_sections = [
            PaperSection(name=name, content=content)
            for name, content in sections.items()
            if content
        ]
        return PaperStruct(title=title, abstract=abstract, sections=normalized_sections)

    def _cleanup(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[\t\x0c]+", " ", text)
        return "\n".join(line.rstrip() for line in text.split("\n")).strip()

    def _split_sections(self, text: str) -> dict[str, str]:
        lines = text.splitlines()
        sections: dict[str, list[str]] = {"Body": []}
        current = "Body"

        for line in lines:
            heading = self._match_heading(line)
            if heading:
                current = heading
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(line)

        return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}

    def _match_heading(self, line: str) -> str | None:
        trimmed = line.strip()
        for heading in self.HEADING_PATTERNS:
            if re.fullmatch(rf"(?:\d+\.?\s*)?{re.escape(heading)}", trimmed, flags=re.IGNORECASE):
                return heading.title()
        return None
