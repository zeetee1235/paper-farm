"""Pipeline artifact models."""

from dataclasses import dataclass


@dataclass(slots=True)
class ExtractedArtifact:
    """Extractor output used by DocStruct/SimpleText backends."""

    raw_text: str
    title_guess: str | None
    abstract_guess: str | None
    section_hints: list[str]
    extractor_name: str


@dataclass(slots=True)
class CleanedArtifact:
    """Legacy normalization model kept for compatibility."""

    cleaned_text: str
    sections: dict[str, str]
    references_detected: bool
    normalizer_name: str


@dataclass(slots=True)
class PaperSection:
    """A normalized section block."""

    name: str
    content: str


@dataclass(slots=True)
class PaperStruct:
    """Standardized paper structure consumed by summarizers."""

    title: str
    abstract: str
    sections: list[PaperSection]


@dataclass(slots=True)
class SummaryResult:
    """Summary contract compatible with agent.md output_contract.json."""

    title: str
    summary: str
    problem: str
    key_idea: str
    method: str
    experiment: str
    results: str
    contributions: list[str]
    limitations: str
    future_work: str
    keywords: list[str]
    obsidian_markdown: str
