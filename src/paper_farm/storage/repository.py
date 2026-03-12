"""File-backed repository for Paper-Farm artifacts."""

from pathlib import Path
import shutil
from typing import Any

from paper_farm.config import Settings
from paper_farm.models.paper import PaperMetadata
from paper_farm.utils.jsonio import read_json, write_json


class PaperRepository:
    """Handles filesystem contracts defined in agent.md."""

    def __init__(self, settings: Settings):
        self._settings = settings
        for path in [
            settings.raw_pdf_root,
            settings.metadata_root,
            settings.parsed_root,
            settings.summary_root,
            settings.obsidian_papers_root,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def raw_pdf_path(self, paper_id: str) -> Path:
        return self._settings.raw_pdf_root / f"{paper_id}.pdf"

    def metadata_path(self, paper_id: str) -> Path:
        return self._settings.metadata_root / f"{paper_id}.json"

    def paper_struct_path(self, paper_id: str) -> Path:
        return self._settings.parsed_root / f"{paper_id}.json"

    def summary_path(self, paper_id: str) -> Path:
        return self._settings.summary_root / f"{paper_id}.json"

    def output_contract_path(self) -> Path:
        return self._settings.summary_root / "output_contract.json"

    def vault_dir(self, paper_id: str) -> Path:
        return self._settings.obsidian_papers_root / paper_id

    def save_raw_pdf(self, paper_id: str, source_pdf: Path) -> Path:
        target = self.raw_pdf_path(paper_id)
        if not target.exists():
            shutil.copy2(source_pdf, target)
        return target

    def save_metadata(self, metadata: PaperMetadata) -> Path:
        path = self.metadata_path(metadata.id)
        write_json(path, metadata)
        return path

    def load_metadata(self, paper_id: str) -> dict[str, Any]:
        return read_json(self.metadata_path(paper_id))

    def save_paper_struct(self, paper_id: str, payload: Any) -> Path:
        path = self.paper_struct_path(paper_id)
        write_json(path, payload)
        return path

    def load_paper_struct(self, paper_id: str) -> dict[str, Any]:
        return read_json(self.paper_struct_path(paper_id))

    def save_summary(self, paper_id: str, payload: Any) -> Path:
        path = self.summary_path(paper_id)
        write_json(path, payload)
        return path

    def load_summary(self, paper_id: str) -> dict[str, Any]:
        return read_json(self.summary_path(paper_id))

    def save_output_contract(self, payload: Any) -> Path:
        path = self.output_contract_path()
        write_json(path, payload)
        return path

    def list_paper_ids(self) -> list[str]:
        return sorted(path.stem for path in self._settings.metadata_root.glob("*.json"))
