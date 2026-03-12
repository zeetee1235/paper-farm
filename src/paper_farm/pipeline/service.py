"""Main pipeline orchestration service aligned with agent.md."""

from dataclasses import asdict
import hashlib
from pathlib import Path
import re

import logging

from paper_farm.config import Settings, language_display_name
from paper_farm.exporters import MarkdownExporter
from paper_farm.extractors import SmartExtractor
from paper_farm.models.artifacts import PaperSection, PaperStruct
from paper_farm.models.paper import PaperMetadata
from paper_farm.normalizers import BasicTextNormalizer
from paper_farm.storage.repository import PaperRepository
from paper_farm.summarizers import LocalSummaryBackend, OllamaSummaryBackend

log = logging.getLogger(__name__)


class PipelineService:
    """Coordinates metadata->paper_struct->summary->obsidian pipeline."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.repo = PaperRepository(settings)
        self.extractor = SmartExtractor()
        self.normalizer = BasicTextNormalizer()
        if settings.llm.backend == "ollama":
            self.summarizer = OllamaSummaryBackend(
                model               = settings.llm.model,
                base_url            = settings.llm.base_url,
                timeout             = settings.llm.timeout,
                language_name       = language_display_name(settings.summary.language),
                section_char_limit  = settings.llm.section_char_limit,
                total_char_limit    = settings.llm.total_char_limit,
            )
        else:
            self.summarizer = LocalSummaryBackend()
        self.exporter = MarkdownExporter()
        self._ensure_output_contract()

    def ingest(
        self,
        pdf_path: Path,
        *,
        title: str | None = None,
        authors: list[str] | None = None,
        year: int | None = None,
        venue: str | None = None,
        doi: str | None = None,
        tags: list[str] | None = None,
        source: str = "zotero-scan",
    ) -> str:
        """Register a PDF and save normalized metadata."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        inferred_title = title or pdf_path.stem.replace("_", " ").strip() or "Untitled Paper"
        paper_id = self._make_paper_id(inferred_title, year, authors, pdf_path)
        saved_pdf = self.repo.save_raw_pdf(paper_id, pdf_path)

        metadata = PaperMetadata(
            id=paper_id,
            title=inferred_title,
            authors=authors or [],
            year=year,
            venue=venue,
            doi=doi,
            pdf_path=str(saved_pdf),
            tags=tags or [],
            source=source,
        )
        self.repo.save_metadata(metadata)
        return paper_id

    def parse(self, paper_id: str) -> Path:
        """Parse raw PDF with extractor + normalizer and save paper_struct.json."""
        metadata = self.repo.load_metadata(paper_id)
        pdf_path = self.repo.raw_pdf_path(paper_id)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Missing raw PDF: {pdf_path}")

        extracted = self.extractor.extract(pdf_path)
        struct = self.normalizer.to_paper_struct(title=metadata["title"], raw_text=extracted.raw_text)
        return self.repo.save_paper_struct(paper_id, asdict(struct))

    def summarize(self, paper_id: str) -> Path:
        """Create summary.json from paper_struct.json."""
        struct_payload = self.repo.load_paper_struct(paper_id)
        struct = PaperStruct(
            title=struct_payload["title"],
            abstract=struct_payload.get("abstract", ""),
            sections=[
                PaperSection(name=section.get("name", "Body"), content=section.get("content", ""))
                for section in struct_payload.get("sections", [])
            ],
        )
        summary = self.summarizer.summarize(struct)
        return self.repo.save_summary(paper_id, asdict(summary))

    def export_obsidian(self, paper_id: str) -> Path:
        """Export Obsidian directory for one paper."""
        metadata = self.repo.load_metadata(paper_id)
        summary = self.repo.load_summary(paper_id)
        return self.exporter.export(
            paper_id=paper_id,
            source_pdf=self.repo.raw_pdf_path(paper_id),
            metadata=metadata,
            summary=summary,
            vault_root=self.settings.obsidian_papers_root,
            summary_root=self.settings.summary_root,
        )

    def run(self, pdf_path: Path, **metadata: object) -> str:
        """Run full pipeline for one PDF, skipping already-completed stages."""
        paper_id = self.ingest(pdf_path, **metadata)
        if not self.repo.paper_struct_path(paper_id).exists():
            self.parse(paper_id)
        if not self.repo.summary_path(paper_id).exists():
            self.summarize(paper_id)
        if not self.repo.vault_dir(paper_id).exists():
            self.export_obsidian(paper_id)
        return paper_id

    def run_all(self) -> list[str]:
        """Process all PDFs currently present under papers/raw_pdf."""
        processed: list[str] = []
        for pdf_path in sorted(self.settings.raw_pdf_root.glob("*.pdf")):
            paper_id = pdf_path.stem
            if not self.repo.metadata_path(paper_id).exists():
                metadata = PaperMetadata(
                    id=paper_id,
                    title=pdf_path.stem,
                    authors=[],
                    year=None,
                    venue=None,
                    doi=None,
                    pdf_path=str(pdf_path),
                    tags=[],
                    source="raw-folder",
                )
                self.repo.save_metadata(metadata)
            self.parse(paper_id)
            self.summarize(paper_id)
            self.export_obsidian(paper_id)
            processed.append(paper_id)
        return processed

    def list_papers(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for paper_id in self.repo.list_paper_ids():
            metadata = self.repo.load_metadata(paper_id)
            rows.append(
                {
                    "id": metadata.get("id", paper_id),
                    "title": metadata.get("title", ""),
                    "year": metadata.get("year"),
                    "authors": metadata.get("authors", []),
                }
            )
        return rows

    def show(self, paper_id: str) -> dict[str, object]:
        metadata = self.repo.load_metadata(paper_id)
        return {
            "metadata": metadata,
            "artifacts": {
                "raw_pdf": self.repo.raw_pdf_path(paper_id).exists(),
                "paper_struct": self.repo.paper_struct_path(paper_id).exists(),
                "summary": self.repo.summary_path(paper_id).exists(),
                "obsidian": self.repo.vault_dir(paper_id).exists(),
            },
        }

    def _ensure_output_contract(self) -> None:
        contract = {
            "title": "",
            "summary": "",
            "problem": "",
            "key_idea": "",
            "method": "",
            "experiment": "",
            "results": "",
            "contributions": [],
            "limitations": "",
            "future_work": "",
            "keywords": [],
            "obsidian_markdown": "",
        }
        if not self.repo.output_contract_path().exists():
            self.repo.save_output_contract(contract)

    @staticmethod
    def _slug(value: str) -> str:
        lowered = value.lower().strip()
        normalized = re.sub(r"[^a-z0-9]+", "_", lowered)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized or "paper"

    def _make_paper_id(
        self,
        title: str,
        year: int | None,
        authors: list[str] | None,
        pdf_path: Path,
    ) -> str:
        author_part = self._slug(authors[0].split()[0]) if authors else "unknown"
        year_part = str(year) if year else "na"
        title_part = self._slug(title)[:40]
        base = f"{author_part}_{year_part}_{title_part}"
        if not self.repo.metadata_path(base).exists():
            return base
        # Same PDF content? Re-use existing ID instead of creating a duplicate.
        incoming_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        existing_pdf = self.repo.raw_pdf_path(base)
        if existing_pdf.exists():
            existing_hash = hashlib.sha256(existing_pdf.read_bytes()).hexdigest()
            if incoming_hash == existing_hash:
                return base
        digest = incoming_hash[:8]
        return f"{base}_{digest}"
