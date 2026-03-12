"""Obsidian exporter for per-paper directory output."""

import json
from pathlib import Path
import shutil

from paper_farm.utils.jsonio import write_json

NOTES_TEMPLATE = """# Notes

[[summary|Summary]] | [[paper.pdf|PDF]]

---

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

        frontmatter = self._build_frontmatter(metadata, summary)
        nav = "[[../index|← Index]] | [[paper.pdf|PDF]] | [[notes|Notes]]\n"
        body = summary.get("obsidian_markdown", "")
        summary_md_path = paper_dir / "summary.md"
        summary_md_path.write_text(f"{frontmatter}\n\n{nav}\n{body}", encoding="utf-8")

        notes_path = paper_dir / "notes.md"
        if not notes_path.exists():
            notes_path.write_text(NOTES_TEMPLATE, encoding="utf-8")

        write_json(paper_dir / "metadata.json", metadata)

        self._update_index(vault_root=vault_root, paper_id=paper_id, metadata=metadata, summary=summary)

        return paper_dir

    @staticmethod
    def _build_frontmatter(metadata: dict, summary: dict) -> str:
        """Build YAML frontmatter from metadata and summary keywords."""
        keywords = summary.get("keywords", [])
        # Convert spaces to hyphens so they work as Obsidian tags
        tags = [kw.replace(" ", "-") for kw in keywords]

        authors = metadata.get("authors", [])
        year = metadata.get("year") or "N/A"
        doi = metadata.get("doi") or ""
        title = metadata.get("title", "")

        lines = ["---"]
        lines.append(f'title: "{title}"')
        if authors:
            lines.append("authors:")
            for a in authors:
                lines.append(f"  - {a}")
        lines.append(f"year: {year}")
        if doi:
            lines.append(f"doi: {doi}")
        if tags:
            lines.append("tags:")
            for tag in tags:
                lines.append(f"  - {tag}")
        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def _update_index(*, vault_root: Path, paper_id: str, metadata: dict, summary: dict) -> None:
        """Rebuild index.md in vault root with links to all paper summaries."""
        index_path = vault_root / "index.md"

        # Collect all existing papers from metadata.json files
        entries: list[dict] = []
        for meta_file in sorted(vault_root.glob("*/metadata.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                pid = meta_file.parent.name
                # Load keywords from summary if available
                summary_file = meta_file.parent / "../.." / "summary" / f"{pid}.json"
                kws: list[str] = []
                if summary_file.exists():
                    try:
                        s = json.loads(summary_file.read_text(encoding="utf-8"))
                        kws = s.get("keywords", [])
                    except Exception:
                        pass
                entries.append({
                    "id": pid,
                    "title": meta.get("title", pid),
                    "year": meta.get("year") or "N/A",
                    "authors": meta.get("authors", []),
                    "keywords": kws or meta.get("tags", []),
                })
            except Exception:
                continue

        lines = [
            "# Paper Index\n",
            f"> 총 {len(entries)}편의 논문\n",
            "",
            "| # | title | year | authors | keywords |",
            "|---|------|------|------|--------|",
        ]
        for i, entry in enumerate(entries, 1):
            title = entry["title"]
            year = entry["year"]
            authors = ", ".join(entry["authors"][:2])
            if len(entry["authors"]) > 2:
                authors += " 외"
            pid = entry["id"]
            kw_str = ", ".join(entry["keywords"][:3])
            lines.append(f"| {i} | [[{pid}/summary\\|{title}]] | {year} | {authors} | {kw_str} |")

        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
