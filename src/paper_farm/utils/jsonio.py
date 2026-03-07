"""JSON serialization helpers."""

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> None:
    """Write JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(data) if is_dataclass(data) else data
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    """Read and parse JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))
