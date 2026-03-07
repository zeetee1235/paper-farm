"""Simple fallback PDF text extractor."""

import logging
from pathlib import Path
import re

from paper_farm.models.artifacts import ExtractedArtifact

logger = logging.getLogger(__name__)


class SimpleTextExtractor:
    """Fallback text extractor for MVP.

    Tries `pypdf` if available. If unavailable or extraction fails,
    decodes bytes with a lossy fallback so downstream stages remain usable.
    """

    name = "simple-text"

    def extract(self, pdf_path: Path) -> ExtractedArtifact:
        raw_text = self._try_pypdf(pdf_path)
        if not raw_text.strip():
            logger.warning("pypdf extraction unavailable/empty; using binary decode fallback")
            raw_text = pdf_path.read_bytes().decode("latin-1", errors="ignore")

        title_guess = self._first_nonempty_line(raw_text)
        abstract_guess = self._extract_abstract(raw_text)
        section_hints = self._section_hints(raw_text)
        return ExtractedArtifact(
            raw_text=raw_text,
            title_guess=title_guess,
            abstract_guess=abstract_guess,
            section_hints=section_hints,
            extractor_name=self.name,
        )

    def _try_pypdf(self, pdf_path: Path) -> str:
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            return ""

        try:
            reader = PdfReader(str(pdf_path))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception as exc:
            logger.warning("pypdf failed: %s", exc)
            return ""

    @staticmethod
    def _first_nonempty_line(text: str) -> str | None:
        for line in text.splitlines():
            value = line.strip()
            if len(value) > 5:
                return value[:200]
        return None

    @staticmethod
    def _extract_abstract(text: str) -> str | None:
        match = re.search(r"(?is)\babstract\b[:\s\n]*(.{80,2000}?)(?:\n\s*\n|\bintroduction\b)", text)
        if not match:
            return None
        return " ".join(match.group(1).split())[:1200]

    @staticmethod
    def _section_hints(text: str) -> list[str]:
        labels = ["abstract", "introduction", "method", "results", "conclusion", "references"]
        lower = text.lower()
        return [name.title() for name in labels if name in lower]
