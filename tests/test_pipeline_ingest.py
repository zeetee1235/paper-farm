from pathlib import Path

from paper_farm.config import Settings
from paper_farm.pipeline import PipelineService


def test_ingest_is_idempotent_for_same_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nFake PDF content for MVP tests\n")

    service = PipelineService(Settings(data_root=tmp_path / "data"))

    paper_id_first = service.ingest(pdf_path)
    paper_id_second = service.ingest(pdf_path)

    assert paper_id_first == paper_id_second
    assert (tmp_path / "data" / "papers" / paper_id_first / "metadata.json").exists()
