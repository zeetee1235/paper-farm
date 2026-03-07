"""Main pipeline orchestration service."""

import logging
from pathlib import Path

from paper_farm.config import Settings
from paper_farm.exporters import MarkdownExporter
from paper_farm.extractors import DocStructExtractorStub, SimpleTextExtractor
from paper_farm.models.artifacts import CleanedArtifact, ExtractedArtifact
from paper_farm.models.paper import PaperMetadata
from paper_farm.normalizers import BasicTextNormalizer
from paper_farm.storage.repository import PaperRepository
from paper_farm.summarizers import AgentPRSummaryBackend, LocalSummaryBackend
from paper_farm.utils.hashing import sha256_file

logger = logging.getLogger(__name__)


class PipelineService:
    """Coordinates end-to-end processing for a single paper."""

    def __init__(self, settings: Settings):
        self.repo = PaperRepository(settings)
        self.extractor = SimpleTextExtractor()
        self.docstruct_stub = DocStructExtractorStub()
        self.normalizer = BasicTextNormalizer()
        self.local_summarizer = LocalSummaryBackend()
        self.agent_backend = AgentPRSummaryBackend()
        self.exporter = MarkdownExporter()

    def ingest(self, pdf_path: Path) -> str:
        """Register a paper from local PDF and persist metadata.

        The paper ID is derived from SHA256 and ingestion is idempotent.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        digest = sha256_file(pdf_path)
        paper_id = digest[:12]
        self.repo.create_paper_dir(paper_id)

        paper_dir = self.repo.paper_dir(paper_id)
        metadata_path = paper_dir / "metadata.json"
        if metadata_path.exists():
            logger.info("Paper %s already registered; reusing existing record", paper_id)
            return paper_id

        self.repo.save_original_pdf(paper_id, pdf_path)
        metadata = PaperMetadata(
            paper_id=paper_id,
            original_filename=pdf_path.name,
            sha256=digest,
        )
        self.repo.save_metadata(paper_id, metadata)
        logger.info("Ingested %s -> %s", pdf_path, paper_id)
        return paper_id

    def extract(self, paper_id: str) -> Path:
        """Run extraction stage and persist extracted.json."""
        pdf_path = self.repo.paper_dir(paper_id) / "original.pdf"
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"Missing source PDF for paper_id={paper_id}. "
                "Run `paper-farm ingest <pdf_path>` first."
            )
        extracted = self.extractor.extract(pdf_path)
        return self.repo.save_artifact(paper_id, "extracted.json", extracted)

    def normalize(self, paper_id: str) -> Path:
        """Run normalization stage and persist cleaned.json."""
        extracted_payload = self.repo.load_artifact(paper_id, "extracted.json")
        extracted = ExtractedArtifact(**extracted_payload)
        cleaned = self.normalizer.normalize(extracted)
        return self.repo.save_artifact(paper_id, "cleaned.json", cleaned)

    def summarize(self, paper_id: str, mode: str) -> Path:
        """Run summary stage in selected mode."""
        cleaned_payload = self.repo.load_artifact(paper_id, "cleaned.json")
        cleaned = CleanedArtifact(**cleaned_payload)
        paper_dir = self.repo.paper_dir(paper_id)

        if mode == "local":
            summary = self.local_summarizer.summarize(paper_id, cleaned, paper_dir)
            return self.repo.save_artifact(paper_id, "summary.local.json", summary)
        if mode == "agent-pr":
            self.agent_backend.summarize(paper_id, cleaned, paper_dir)
            return paper_dir / "agent_package"
        raise ValueError(f"Unsupported summary mode: {mode}")

    def export(self, paper_id: str, source: str = "local") -> Path:
        """Export markdown note from summary artifact."""
        if source != "local":
            raise ValueError("MVP exporter currently supports only --source local")

        metadata = self.repo.load_metadata(paper_id)
        summary = self.repo.load_artifact(paper_id, "summary.local.json")
        output_path = self.repo.paper_dir(paper_id) / "note.local.md"
        return self.exporter.export(metadata, summary, output_path)

    def run(self, pdf_path: Path, summary_mode: str = "local") -> str:
        """Run ingest -> extract -> normalize -> summarize -> export."""
        paper_id = self.ingest(pdf_path)
        self.extract(paper_id)
        self.normalize(paper_id)
        self.summarize(paper_id, summary_mode)
        if summary_mode == "local":
            self.export(paper_id, source="local")
        return paper_id

    def list_papers(self) -> list[dict[str, str]]:
        """List papers with minimal metadata."""
        items: list[dict[str, str]] = []
        for paper_id in self.repo.list_papers():
            metadata = self.repo.load_metadata(paper_id)
            items.append(
                {
                    "paper_id": paper_id,
                    "title": metadata.get("title") or metadata.get("original_filename", ""),
                    "created_at": metadata.get("created_at", ""),
                }
            )
        return items

    def show(self, paper_id: str) -> dict:
        """Show known metadata and artifact availability for one paper."""
        paper_dir = self.repo.paper_dir(paper_id)
        metadata = self.repo.load_metadata(paper_id)
        return {
            "metadata": metadata,
            "artifacts": {
                "extracted": (paper_dir / "extracted.json").exists(),
                "cleaned": (paper_dir / "cleaned.json").exists(),
                "summary_local": (paper_dir / "summary.local.json").exists(),
                "note_local": (paper_dir / "note.local.md").exists(),
                "agent_package": (paper_dir / "agent_package").exists(),
            },
        }
