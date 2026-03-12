"""DocStruct CLI-backed extractor with fallback support."""

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Protocol

from paper_farm.models.artifacts import ExtractedArtifact

logger = logging.getLogger(__name__)


class _FallbackExtractor(Protocol):
    def extract(self, pdf_path: Path) -> ExtractedArtifact:
        ...


class DocStructExtractor:
    """Extraction backend using the DocStruct CLI binary."""

    name = "docstruct"

    def __init__(
        self,
        fallback: _FallbackExtractor | None = None,
        docstruct_bin: Path | None = None,
        dpi: int = 120,
        timeout_sec: int = 900,
    ) -> None:
        self.fallback = fallback
        self.docstruct_bin = docstruct_bin
        self.dpi = dpi
        self.timeout_sec = timeout_sec

    def extract(self, pdf_path: Path) -> ExtractedArtifact:
        try:
            raw_text = self._extract_with_docstruct(pdf_path)
        except Exception as exc:
            if self.fallback is None:
                raise
            logger.warning("DocStruct extraction failed, falling back: %s", exc)
            return self.fallback.extract(pdf_path)

        return ExtractedArtifact(
            raw_text=raw_text,
            title_guess=self._first_nonempty_line(raw_text),
            abstract_guess=self._extract_abstract(raw_text),
            section_hints=self._section_hints(raw_text),
            extractor_name=self.name,
        )

    def _extract_with_docstruct(self, pdf_path: Path) -> str:
        bin_path = self._resolve_docstruct_bin()
        if bin_path is None:
            raise FileNotFoundError(
                "DocStruct binary not found. Build submodule with "
                "`cargo build --release --manifest-path external/DocStruct/Cargo.toml` "
                "or set DOCSTRUCT_BIN."
            )

        workdir = self._resolve_docstruct_workdir(bin_path)
        with TemporaryDirectory(prefix="paper_farm_docstruct_") as temp_dir:
            output_dir = Path(temp_dir) / "out"
            cmd = [
                str(bin_path),
                "convert",
                str(pdf_path.resolve()),
                "--output",
                str(output_dir),
                "--dpi",
                str(self.dpi),
                "--quiet",
            ]
            env = os.environ.copy()
            env.setdefault("DOCSTRUCT_PYTHON", sys.executable)
            if workdir is not None:
                bridge = workdir / "ocr" / "bridge" / "ocr_bridge.py"
                if bridge.exists():
                    env["DOCSTRUCT_BRIDGE"] = str(bridge)
            completed = subprocess.run(
                cmd,
                cwd=str(workdir) if workdir is not None else None,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_sec,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.strip()
                raise RuntimeError(f"DocStruct convert failed ({completed.returncode}): {stderr}")

            text_path = output_dir / "document.txt"
            if text_path.exists():
                return text_path.read_text(encoding="utf-8", errors="ignore")

            json_path = output_dir / "document.json"
            if json_path.exists():
                return self._text_from_docstruct_json(json_path)

            raise FileNotFoundError(f"DocStruct output not found in {output_dir}")

    def _resolve_docstruct_bin(self) -> Path | None:
        if self.docstruct_bin is not None:
            return self.docstruct_bin if self.docstruct_bin.exists() else None

        env_value = os.environ.get("DOCSTRUCT_BIN")
        env_path = Path(env_value) if env_value else None
        if env_path is not None and env_path.exists():
            return env_path

        repo_root = Path(__file__).resolve().parents[3]
        local_bin = repo_root / "external" / "DocStruct" / "target" / "release" / "docstruct"
        if local_bin.exists():
            return local_bin

        path_bin = shutil.which("docstruct")
        if path_bin:
            return Path(path_bin)
        return None

    @staticmethod
    def _resolve_docstruct_workdir(bin_path: Path) -> Path | None:
        repo_root = Path(__file__).resolve().parents[3]
        local_submodule = repo_root / "external" / "DocStruct"
        if local_submodule.exists():
            return local_submodule

        if (
            len(bin_path.parts) >= 3
            and bin_path.parent.name == "release"
            and bin_path.parent.parent.name == "target"
        ):
            candidate = bin_path.parent.parent.parent
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _text_from_docstruct_json(json_path: Path) -> str:
        payload = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
        lines: list[str] = []
        for page in payload.get("pages", []):
            for block in page.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = (span.get("text") or "").strip()
                        if text:
                            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _first_nonempty_line(text: str) -> str | None:
        for line in text.splitlines():
            value = line.strip()
            if len(value) > 5:
                return value[:200]
        return None

    @staticmethod
    def _extract_abstract(text: str) -> str | None:
        match = re.search(r"(?is)\babstract\b[:\s\n]*(.{80,2000}?)(?:\n\s*\n|\bintroduction\b)", text)
        if not match:
            return None
        return " ".join(match.group(1).split())[:1200]

    @staticmethod
    def _section_hints(text: str) -> list[str]:
        labels = ["abstract", "introduction", "method", "results", "conclusion", "references"]
        lower = text.lower()
        return [name.title() for name in labels if name in lower]


class DocStructExtractorStub(DocStructExtractor):
    """Backward-compatible alias for previous stub class name."""
