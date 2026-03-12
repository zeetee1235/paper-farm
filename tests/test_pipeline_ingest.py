from pathlib import Path

from paper_farm.config import Settings
from paper_farm.pipeline import PipelineService


def test_ingest_creates_normalized_metadata_and_raw_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nAbstract\nTest abstract text\n")

    service = PipelineService(Settings(project_root=tmp_path))
    paper_id = service.ingest(
        pdf_path,
        title="RPL Routing",
        authors=["Winter T."],
        year=2012,
        venue="IETF",
        doi="10.17487/RFC6550",
        tags=["WSN", "IoT"],
    )

    assert (tmp_path / "papers" / "raw_pdf" / f"{paper_id}.pdf").exists()
    assert (tmp_path / "metadata" / "normalized" / f"{paper_id}.json").exists()
