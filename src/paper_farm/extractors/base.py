"""Extractor interfaces."""

from pathlib import Path
from typing import Protocol

from paper_farm.models.artifacts import ExtractedArtifact


class Extractor(Protocol):
    """Interface for extraction backends."""

    name: str

    def extract(self, pdf_path: Path) -> ExtractedArtifact:
        """Extract textual content from a PDF."""
