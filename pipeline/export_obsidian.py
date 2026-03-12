"""Export one paper into Obsidian folder."""

import argparse

from paper_farm.config import default_settings
from paper_farm.pipeline import PipelineService


def main() -> None:
    parser = argparse.ArgumentParser(description="Export one paper to Obsidian")
    parser.add_argument("paper_id")
    args = parser.parse_args()

    service = PipelineService(default_settings())
    output = service.export_obsidian(args.paper_id)
    print(output)


if __name__ == "__main__":
    main()
