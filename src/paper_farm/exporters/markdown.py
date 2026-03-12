"""Obsidian exporter for per-paper directory output."""

from pathlib import Path
import shutil

from paper_farm.utils.jsonio import write_json

NOTES_TEMPLATE = """# Notes

## Research Ideas

-

## Questions

-

## Follow-up Papers

-
"""


class MarkdownExporter:
    """Export summary + notes + metadata into obsidian vault layout."""

    def export(self, *, paper_id: str, source_pdf: Path, metadata: dict, summary: dict, vault_root: Path) -> Path:
        paper_dir = vault_root / paper_id
        paper_dir.mkdir(parents=True, exist_ok=True)

        pdf_target = paper_dir / "paper.pdf"
        if not pdf_target.exists():
            shutil.copy2(source_pdf, pdf_target)

        summary_md_path = paper_dir / "summary.md"
        summary_md_path.write_text(summary.get("obsidian_markdown", ""), encoding="utf-8")

        notes_path = paper_dir / "notes.md"
        if not notes_path.exists():
            notes_path.write_text(NOTES_TEMPLATE, encoding="utf-8")

        write_json(paper_dir / "metadata.json", metadata)
        return paper_dir
