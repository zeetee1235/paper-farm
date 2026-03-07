"""File-backed repository for paper artifacts."""

from pathlib import Path
import shutil
from typing import Any

from paper_farm.config import Settings
from paper_farm.models.paper import PaperMetadata
from paper_farm.utils.jsonio import read_json, write_json


class PaperRepository:
    """Handles local file layout under `data/papers/<paper_id>/`."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._settings.papers_root.mkdir(parents=True, exist_ok=True)

    def paper_dir(self, paper_id: str) -> Path:
        """Return paper directory for paper ID."""
        return self._settings.papers_root / paper_id

    def paper_exists(self, paper_id: str) -> bool:
        """Return whether paper directory exists."""
        return self.paper_dir(paper_id).exists()

    def create_paper_dir(self, paper_id: str) -> Path:
        """Create and return paper directory if missing."""
        path = self.paper_dir(paper_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_original_pdf(self, paper_id: str, source_pdf: Path) -> Path:
        """Copy source PDF into local paper storage."""
        target = self.paper_dir(paper_id) / "original.pdf"
        shutil.copy2(source_pdf, target)
        return target

    def save_metadata(self, paper_id: str, metadata: PaperMetadata) -> Path:
        """Persist metadata.json."""
        path = self.paper_dir(paper_id) / "metadata.json"
        write_json(path, metadata)
        return path

    def load_metadata(self, paper_id: str) -> dict[str, Any]:
        """Load metadata.json as dictionary."""
        return read_json(self.paper_dir(paper_id) / "metadata.json")

    def save_artifact(self, paper_id: str, filename: str, payload: Any) -> Path:
        """Persist an arbitrary JSON artifact."""
        path = self.paper_dir(paper_id) / filename
        write_json(path, payload)
        return path

    def load_artifact(self, paper_id: str, filename: str) -> dict[str, Any]:
        """Load a JSON artifact."""
        return read_json(self.paper_dir(paper_id) / filename)

    def list_papers(self) -> list[str]:
        """List known paper IDs that contain metadata.json."""
        if not self._settings.papers_root.exists():
            return []
        paper_ids: list[str] = []
        for path in sorted(self._settings.papers_root.iterdir()):
            if path.is_dir() and (path / "metadata.json").exists():
                paper_ids.append(path.name)
        return paper_ids
