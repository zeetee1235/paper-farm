"""Text normalization for extracted paper text."""

import re

from paper_farm.models.artifacts import CleanedArtifact, ExtractedArtifact


class BasicTextNormalizer:
    """Simple deterministic text cleaner + section detector."""

    name = "basic-text"

    HEADING_PATTERNS = [
        "Abstract",
        "Introduction",
        "Method",
        "Methods",
        "Results",
        "Discussion",
        "Conclusion",
        "References",
    ]

    def normalize(self, extracted: ExtractedArtifact) -> CleanedArtifact:
        cleaned_text = self._cleanup(extracted.raw_text)
        sections = self._split_sections(cleaned_text)
        references_detected = "references" in cleaned_text.lower()
        return CleanedArtifact(
            cleaned_text=cleaned_text,
            sections=sections,
            references_detected=references_detected,
            normalizer_name=self.name,
        )

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
