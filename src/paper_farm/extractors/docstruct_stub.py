"""DocStruct integration stub."""

from pathlib import Path

from paper_farm.models.artifacts import ExtractedArtifact


class DocStructExtractorStub:
    """Placeholder extractor for future DocStruct integration."""

    name = "docstruct-stub"

    def extract(self, pdf_path: Path) -> ExtractedArtifact:
        raise NotImplementedError(
            "DocStruct extractor is not implemented in MVP. "
            "Use SimpleTextExtractor for now."
        )
