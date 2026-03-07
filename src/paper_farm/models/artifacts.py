"""Pipeline artifact models."""

from dataclasses import dataclass


@dataclass(slots=True)
class ExtractedArtifact:
    """Result produced by an extraction backend."""

    raw_text: str
    title_guess: str | None
    abstract_guess: str | None
    section_hints: list[str]
    extractor_name: str


@dataclass(slots=True)
class CleanedArtifact:
    """Result produced by the text normalizer."""

    cleaned_text: str
    sections: dict[str, str]
    references_detected: bool
    normalizer_name: str


@dataclass(slots=True)
class SummaryResult:
    """Stable summary schema shared across summary backends."""

    mode: str
    one_line: str
    short_summary: str
    contributions: list[str]
    methods: list[str]
    experiments: list[str]
    limitations: list[str]
    keywords: list[str]
