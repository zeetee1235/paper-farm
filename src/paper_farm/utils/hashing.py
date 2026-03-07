"""Hashing helpers."""

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Compute SHA256 for a file path."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
