"""CLI entrypoint for paper-farm."""

import json
from pathlib import Path

import typer

from paper_farm.config import default_settings, load_settings
from paper_farm.logging import configure_logging
from paper_farm.pipeline import PipelineService

app = typer.Typer(help="paper-farm: Zotero → LLM summarization → Obsidian pipeline")

_CONFIG_TEMPLATE = """\
# paper-farm configuration file
# Paths support ~ (home directory) expansion

[paths]
# Path to Zotero storage folder (update to your actual path)
# macOS:   ~/Zotero/storage
# Linux:   ~/snap/zotero-snap/common/Zotero/storage
# Windows: ~/Zotero/storage
# project_root = "."    # paper-farm data directory (default: current dir)

[llm]
# "ollama" or "rule-based"
backend = "ollama"
model = "phi4:14b"           # run: ollama pull phi4:14b
base_url = "http://localhost:11434"
timeout = 600

[summary]
# Output language: "en"=English, "ko"=Korean, "ja"=Japanese, "zh"=Chinese
language = "en"

[watcher]
zotero_storage = "~/Zotero/storage"
poll_interval = 30             # seconds between scans
"""


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging")) -> None:
    configure_logging(verbose)


def _service() -> PipelineService:
    return PipelineService(default_settings())


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@app.command("init-config")
def init_config(
    output: Path = typer.Option(Path("paper-farm.toml"), "--output", "-o", help="Output config file path"),
) -> None:
    """Generate a paper-farm.toml config template."""
    if output.exists():
        typer.echo(f"Already exists: {output}")
        raise typer.Exit(1)
    output.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
    typer.echo(f"Config created: {output}")
    typer.echo("Edit the file and set your zotero_storage and obsidian_vault paths.")


# ---------------------------------------------------------------------------
# Pipeline commands (manual)
# ---------------------------------------------------------------------------

@app.command()
def ingest(
    pdf_path: Path,
    title: str | None = typer.Option(None, "--title"),
    authors: str = typer.Option("", "--authors", help="Comma-separated author list"),
    year: int | None = typer.Option(None, "--year"),
    venue: str | None = typer.Option(None, "--venue"),
    doi: str | None = typer.Option(None, "--doi"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
) -> None:
    """Register a PDF and save normalized metadata."""
    paper_id = _service().ingest(
        pdf_path,
        title=title,
        authors=[x.strip() for x in authors.split(",") if x.strip()],
        year=year,
        venue=venue,
        doi=doi,
        tags=[x.strip() for x in tags.split(",") if x.strip()],
    )
    typer.echo(paper_id)


@app.command()
def parse(paper_id: str) -> None:
    """Parse PDF into paper_struct.json."""
    out = _service().parse(paper_id)
    typer.echo(str(out))


@app.command()
def summarize(paper_id: str) -> None:
    """Generate summary.json from paper_struct.json."""
    out = _service().summarize(paper_id)
    typer.echo(str(out))


@app.command("export")
def export_cmd(paper_id: str) -> None:
    """Export Obsidian directory for a paper."""
    out = _service().export_obsidian(paper_id)
    typer.echo(str(out))


@app.command()
def run(
    pdf_path: Path,
    title: str | None = typer.Option(None, "--title"),
    authors: str = typer.Option("", "--authors"),
    year: int | None = typer.Option(None, "--year"),
    venue: str | None = typer.Option(None, "--venue"),
    doi: str | None = typer.Option(None, "--doi"),
    tags: str = typer.Option("", "--tags"),
) -> None:
    """Run full pipeline (ingest→parse→summarize→export) for one PDF."""
    paper_id = _service().run(
        pdf_path,
        title=title,
        authors=[x.strip() for x in authors.split(",") if x.strip()],
        year=year,
        venue=venue,
        doi=doi,
        tags=[x.strip() for x in tags.split(",") if x.strip()],
    )
    typer.echo(paper_id)


@app.command("run-all")
def run_all_cmd() -> None:
    """Process all PDFs under papers/raw_pdf/."""
    processed = _service().run_all()
    typer.echo(json.dumps(processed, ensure_ascii=False, indent=2))


@app.command("list")
def list_cmd() -> None:
    """List all registered papers."""
    rows = _service().list_papers()
    typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))


@app.command()
def show(paper_id: str) -> None:
    """Show paper metadata and artifact status."""
    info = _service().show(paper_id)
    typer.echo(json.dumps(info, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Zotero watcher
# ---------------------------------------------------------------------------

@app.command()
def watch(
    config: Path = typer.Option(Path("paper-farm.toml"), "--config", "-c", help="Config file path"),
    once: bool = typer.Option(False, "--once", help="Scan once and exit"),
) -> None:
    """Watch Zotero storage and auto-process new PDFs.

    Requires a paper-farm.toml config file:

        paper-farm init-config
    """
    from paper_farm.watchers import ZoteroWatcher

    if not config.exists():
        typer.echo(f"Config file not found: {config}")
        typer.echo("Create one first:")
        typer.echo("  paper-farm init-config")
        raise typer.Exit(1)

    settings = load_settings(config)
    watcher = ZoteroWatcher(settings)

    if once:
        new_ids = watcher.scan_once()
        typer.echo(json.dumps(new_ids, ensure_ascii=False, indent=2))
    else:
        try:
            watcher.run_forever()
        except KeyboardInterrupt:
            typer.echo("\nWatcher stopped.")


if __name__ == "__main__":
    app()
