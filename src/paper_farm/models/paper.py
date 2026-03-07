"""Paper metadata model."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class PaperMetadata:
    """Represents a registered paper in local storage."""

    paper_id: str
    original_filename: str
    sha256: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    source: str = "local"
