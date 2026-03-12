"""Run full pipeline for all PDFs in papers/raw_pdf."""

from paper_farm.config import default_settings
from paper_farm.pipeline import PipelineService


def main() -> None:
    service = PipelineService(default_settings())
    for paper_id in service.run_all():
        print(paper_id)


if __name__ == "__main__":
    main()
