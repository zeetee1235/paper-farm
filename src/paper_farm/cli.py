"""CLI entrypoint for paper-farm."""

from enum import Enum
import json
from pathlib import Path

import typer

from paper_farm.config import default_settings
from paper_farm.logging import configure_logging
from paper_farm.pipeline import PipelineService

app = typer.Typer(help="paper-farm: local-first paper ingestion and summarization MVP")


class SummaryMode(str, Enum):
    """Supported summary mode options."""

    local = "local"
    agent_pr = "agent-pr"


class ExportSource(str, Enum):
    """Supported exporter source options."""

    local = "local"


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging.")) -> None:
    """CLI callback for global options."""
    configure_logging(verbose)


def _service() -> PipelineService:
    return PipelineService(default_settings())


@app.command()
def ingest(pdf_path: Path) -> None:
    """Register a paper from a local PDF file."""
    paper_id = _service().ingest(pdf_path)
    typer.echo(paper_id)


@app.command()
def extract(paper_id: str) -> None:
    """Extract text from a registered paper."""
    out = _service().extract(paper_id)
    typer.echo(str(out))


@app.command()
def normalize(paper_id: str) -> None:
    """Normalize extracted paper text."""
    out = _service().normalize(paper_id)
    typer.echo(str(out))


@app.command()
def summarize(
    paper_id: str,
    mode: SummaryMode = typer.Option(SummaryMode.local, "--mode", help="Summary mode: local or agent-pr"),
) -> None:
    """Produce summary artifacts."""
    out = _service().summarize(paper_id, mode=mode.value)
    typer.echo(str(out))


@app.command()
def export(
    paper_id: str,
    source: ExportSource = typer.Option(ExportSource.local, "--source", help="Summary source mode for export."),
) -> None:
    """Export a markdown note."""
    out = _service().export(paper_id, source=source.value)
    typer.echo(str(out))


@app.command()
def run(
    pdf_path: Path,
    summary_mode: SummaryMode = typer.Option(SummaryMode.local, "--summary-mode", help="Summary mode used by run."),
) -> None:
    """Run full pipeline for one PDF."""
    paper_id = _service().run(pdf_path, summary_mode=summary_mode.value)
    typer.echo(paper_id)


@app.command("list")
def list_cmd() -> None:
    """List registered papers."""
    rows = _service().list_papers()
    typer.echo(json.dumps(rows, indent=2))


@app.command()
def show(paper_id: str) -> None:
    """Show metadata and artifact status for one paper."""
    info = _service().show(paper_id)
    typer.echo(json.dumps(info, indent=2))


if __name__ == "__main__":
    app()
