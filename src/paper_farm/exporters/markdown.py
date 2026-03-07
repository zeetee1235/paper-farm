"""Markdown note exporter."""

from pathlib import Path


class MarkdownExporter:
    """Builds Obsidian-friendly markdown notes from summary artifacts."""

    def export(self, metadata: dict, summary: dict, output_path: Path) -> Path:
        title = metadata.get("title") or summary.get("one_line") or metadata.get("original_filename", "Untitled")
        keywords = " ".join(f"#{k.replace(' ', '_')}" for k in summary.get("keywords", []))

        content = f"""# {title}

## Metadata
- Authors: {", ".join(metadata.get("authors") or [])}
- Year: {metadata.get("year") or ""}
- Source: {metadata.get("source") or ""}
- Paper ID: {metadata.get("paper_id")}

## One-line summary
{summary.get("one_line", "")}

## Short summary
{summary.get("short_summary", "")}

## Contributions
{self._to_bullets(summary.get("contributions", []))}

## Methods
{self._to_bullets(summary.get("methods", []))}

## Experiments
{self._to_bullets(summary.get("experiments", []))}

## Limitations
{self._to_bullets(summary.get("limitations", []))}

## Keywords
{keywords}
"""
        output_path.write_text(content.strip() + "\n", encoding="utf-8")
        return output_path

    @staticmethod
    def _to_bullets(items: list[str]) -> str:
        if not items:
            return "-"
        return "\n".join(f"- {item}" for item in items)
