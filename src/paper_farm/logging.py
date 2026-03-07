"""Logging configuration utilities."""

import logging


def configure_logging(verbose: bool = False) -> None:
    """Configure root logging once for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
