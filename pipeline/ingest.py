"""Ingest one PDF into Paper-Farm metadata store."""

from pathlib import Path
import argparse

from paper_farm.config import default_settings
from paper_farm.pipeline import PipelineService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one paper PDF")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--title", default=None)
    parser.add_argument("--authors", default="")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--venue", default=None)
    parser.add_argument("--doi", default=None)
    parser.add_argument("--tags", default="")
    args = parser.parse_args()

    service = PipelineService(default_settings())
    paper_id = service.ingest(
        args.pdf,
        title=args.title,
        authors=[x.strip() for x in args.authors.split(",") if x.strip()],
        year=args.year,
        venue=args.venue,
        doi=args.doi,
        tags=[x.strip() for x in args.tags.split(",") if x.strip()],
    )
    print(paper_id)


if __name__ == "__main__":
    main()
