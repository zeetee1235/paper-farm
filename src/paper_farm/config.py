"""Configuration helpers for Paper-Farm path layout."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class LLMSettings:
    backend: str   = "rule-based"           # "rule-based" | "ollama"
    model: str     = "llama3:8b"
    base_url: str  = "http://localhost:11434"
    timeout: int   = 300
    # How much text to send to the LLM per section / total
    section_char_limit: int = 2000
    total_char_limit: int   = 16000


@dataclass(slots=True)
class SummarySettings:
    # Output language for summaries.  Any IETF-style tag or plain name works;
    # "ko" → Korean, "en" → English, "ja" → Japanese, "zh" → Chinese, etc.
    language: str = "ko"


@dataclass(slots=True)
class WatcherSettings:
    poll_interval: int  = 30       # seconds between Zotero scans
    zotero_storage: Path = field(
        default_factory=lambda: Path("~/.zotero/storage").expanduser()
    )


@dataclass(slots=True)
class Settings:
    """All application settings, loaded from paper-farm.toml."""

    project_root:   Path           = field(default_factory=Path.cwd)
    obsidian_vault: Path | None    = None
    llm:     LLMSettings     = field(default_factory=LLMSettings)
    summary: SummarySettings = field(default_factory=SummarySettings)
    watcher: WatcherSettings = field(default_factory=WatcherSettings)

    # ------------------------------------------------------------------
    # Internal layout (relative to project_root)
    # ------------------------------------------------------------------

    @property
    def data_root(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_pdf_root(self) -> Path:
        return self.data_root / "raw_pdf"

    @property
    def metadata_root(self) -> Path:
        return self.data_root / "metadata"

    @property
    def parsed_root(self) -> Path:
        return self.data_root / "parsed"

    @property
    def summary_root(self) -> Path:
        return self.data_root / "summary"

    @property
    def obsidian_papers_root(self) -> Path:
        if self.obsidian_vault is not None:
            return self.obsidian_vault
        return self.project_root / "obsidian" / "vault" / "papers"


# ---------------------------------------------------------------------------
# Language display name helper
# ---------------------------------------------------------------------------

_LANG_NAMES: dict[str, str] = {
    "ko": "Korean",
    "en": "English",
    "ja": "Japanese",
    "zh": "Chinese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}


def language_display_name(code: str) -> str:
    """Return a human-readable language name for the system prompt."""
    return _LANG_NAMES.get(code.lower(), code)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _find_config_file() -> Path | None:
    """Search for paper-farm.toml up from cwd."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / "paper-farm.toml"
        if candidate.exists():
            return candidate
    return None


def load_settings(config_path: Path | None = None) -> Settings:
    """Load Settings from paper-farm.toml; falls back to defaults if missing."""
    path = config_path or _find_config_file()
    if path is None or not path.exists():
        return Settings()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    paths        = data.get("paths", {})
    llm_data     = data.get("llm", {})
    summary_data = data.get("summary", {})
    watcher_data = data.get("watcher", {})

    project_root = Path(paths.get("project_root", ".")).expanduser()

    obsidian_raw = paths.get("obsidian_vault")
    obsidian_vault = Path(obsidian_raw).expanduser() if obsidian_raw else None

    zotero_raw = watcher_data.get("zotero_storage", "~/.zotero/storage")

    return Settings(
        project_root=project_root,
        obsidian_vault=obsidian_vault,
        llm=LLMSettings(
            backend            = llm_data.get("backend", "rule-based"),
            model              = llm_data.get("model", "llama3:8b"),
            base_url           = llm_data.get("base_url", "http://localhost:11434"),
            timeout            = int(llm_data.get("timeout", 300)),
            section_char_limit = int(llm_data.get("section_char_limit", 2000)),
            total_char_limit   = int(llm_data.get("total_char_limit", 16000)),
        ),
        summary=SummarySettings(
            language = summary_data.get("language", "ko"),
        ),
        watcher=WatcherSettings(
            poll_interval  = int(watcher_data.get("poll_interval", 30)),
            zotero_storage = Path(zotero_raw).expanduser(),
        ),
    )


def default_settings() -> Settings:
    """Return settings loaded from paper-farm.toml (or defaults)."""
    return load_settings()
