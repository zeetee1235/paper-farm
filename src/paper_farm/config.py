"""Configuration helpers for local data paths."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    """Application settings for paths and defaults."""

    data_root: Path = Path("data")

    @property
    def papers_root(self) -> Path:
        """Directory containing per-paper artifacts."""
        return self.data_root / "papers"


def default_settings() -> Settings:
    """Return default settings."""
    return Settings()
