"""Obsidian exporter for per-paper directory output."""

import json
from pathlib import Path
import re
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


def _vault_folder_name(paper_id: str, paper_num: int | None) -> str:
    """Return the vault folder name, prefixed with zero-padded number if available."""
    if paper_num is not None:
        return f"{paper_num:03d}_{paper_id}"
    return paper_id


class MarkdownExporter:
    """Export summary + notes + metadata into obsidian vault layout."""

    def export(
        self,
        *,
        paper_id: str,
        source_pdf: Path,
        metadata: dict,
        summary: dict,
        vault_root: Path,
        summary_root: Path | None = None,
    ) -> Path:
        paper_num = metadata.get("paper_num")
        if paper_num is None:
            paper_num = self._assign_next_paper_num(vault_root)
            metadata["paper_num"] = paper_num
        folder_name = _vault_folder_name(paper_id, paper_num)
        paper_dir = vault_root / folder_name
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

        self._update_index(
            vault_root=vault_root,
            paper_id=paper_id,
            metadata=metadata,
            summary=summary,
            summary_root=summary_root,
        )

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
    def _assign_next_paper_num(vault_root: Path) -> int:
        """Return the next available paper_num by scanning existing vault folders."""
        max_num = 0
        for meta_file in vault_root.glob("*/metadata.json"):
            try:
                m = json.loads(meta_file.read_text(encoding="utf-8"))
                num = m.get("paper_num")
                if isinstance(num, int):
                    max_num = max(max_num, num)
            except Exception:
                pass
        return max_num + 1

    @staticmethod
    def _update_index(
        *,
        vault_root: Path,
        paper_id: str,
        metadata: dict,
        summary: dict,
        summary_root: Path | None = None,
    ) -> None:
        """Rebuild index.md in vault root with links to all paper summaries."""
        index_path = vault_root / "index.md"

        entries: list[dict] = []
        for meta_file in sorted(vault_root.glob("*/metadata.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                folder_name = meta_file.parent.name
                # paper_id is stored in metadata; fall back to stripping NNN_ prefix
                pid = meta.get("id") or re.sub(r"^\d+_", "", folder_name)
                num = meta.get("paper_num")

                kws: list[str] = []
                if pid == paper_id:
                    kws = summary.get("keywords", [])
                elif summary_root is not None:
                    summary_file = summary_root / f"{pid}.json"
                    if summary_file.exists():
                        try:
                            s = json.loads(summary_file.read_text(encoding="utf-8"))
                            kws = s.get("keywords", [])
                        except Exception:
                            pass

                authors = meta.get("authors", [])
                year = meta.get("year")
                if not authors:
                    authors = MarkdownExporter._infer_authors_from_title(meta.get("title", pid))
                if year in (None, "", "N/A"):
                    year = MarkdownExporter._infer_year_from_title(meta.get("title", pid)) or "N/A"
                entries.append({
                    "num": num,
                    "folder": folder_name,
                    "title": meta.get("title", pid),
                    "year": year,
                    "authors": authors,
                    "keywords": kws or meta.get("tags", []),
                })
            except Exception:
                continue

        # Sort by paper_num so the table order is stable
        entries.sort(key=lambda e: (e["num"] is None, e["num"] or 0))

        lines = [
            "# Paper Index\n",
            f"> total {len(entries)} papers\n",
            "",
            "| # | title | year | authors | keywords |",
            "|---|------|------|------|--------|",
        ]
        for entry in entries:
            num_str = f"{entry['num']:03d}" if entry["num"] is not None else "—"
            title = entry["title"]
            year = entry["year"]
            authors = ", ".join(entry["authors"][:2])
            if len(entry["authors"]) > 2:
                authors += " et al."
            folder = entry["folder"]
            kw_str = ", ".join(entry["keywords"][:3])
            lines.append(f"| {num_str} | [[{folder}/summary\\|{title}]] | {year} | {authors} | {kw_str} |")

        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _infer_authors_from_title(title: str) -> list[str]:
        match = re.match(r"^(.*?)\s*-\s*\d{4}\s*-", title)
        if not match:
            return []
        author_text = match.group(1).strip()
        return [author_text] if author_text else []

    @staticmethod
    def _infer_year_from_title(title: str) -> int | None:
        match = re.search(r"\b(19|20)\d{2}\b", title)
        return int(match.group(0)) if match else None
