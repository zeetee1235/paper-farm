"""Paper metadata models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class PaperMetadata:
    """Normalized metadata used throughout the pipeline."""

    id: str
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    doi: str | None
    pdf_path: str
    tags: list[str] = field(default_factory=list)
    source: str = "zotero-scan"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
