from pathlib import Path

from paper_farm.config import Settings
from paper_farm.pipeline import PipelineService


def test_end_to_end_generates_summary_and_obsidian_bundle(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(
        (
            "%PDF-1.4\n"
            "Abstract\n"
            "This paper presents a method for low-power routing.\n\n"
            "Method\n"
            "We use a lightweight architecture.\n\n"
            "Results\n"
            "Evaluation shows improved packet delivery.\n"
        ).encode("utf-8")
    )

    service = PipelineService(Settings(project_root=tmp_path))
    paper_id = service.run(pdf_path, title="Low-Power Routing")

    assert (tmp_path / "parsed" / "paper_struct" / f"{paper_id}.json").exists()
    assert (tmp_path / "summary" / f"{paper_id}.json").exists()
    assert (tmp_path / "summary" / "output_contract.json").exists()
    assert (tmp_path / "obsidian" / "vault" / "papers" / paper_id / "paper.pdf").exists()
    assert (tmp_path / "obsidian" / "vault" / "papers" / paper_id / "summary.md").exists()
    assert (tmp_path / "obsidian" / "vault" / "papers" / paper_id / "notes.md").exists()
    assert (tmp_path / "obsidian" / "vault" / "papers" / paper_id / "metadata.json").exists()
