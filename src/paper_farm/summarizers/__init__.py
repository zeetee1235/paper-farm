"""Summary backends."""

from .local_backend import LocalSummaryBackend
from .ollama_backend import OllamaSummaryBackend

__all__ = ["LocalSummaryBackend", "OllamaSummaryBackend"]
