"""Summary backend interfaces."""

from pathlib import Path
from typing import Protocol

from paper_farm.models.artifacts import CleanedArtifact, SummaryResult


class SummaryBackend(Protocol):
    """Pluggable summary backend interface."""

    mode: str

    def summarize(self, paper_id: str, cleaned: CleanedArtifact, paper_dir: Path) -> SummaryResult | None:
        """Generate summary output or side-effects for a paper."""
