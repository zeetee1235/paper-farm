from paper_farm.models.artifacts import ExtractedArtifact
from paper_farm.normalizers import BasicTextNormalizer


def test_normalizer_detects_sections_and_references() -> None:
    extracted = ExtractedArtifact(
        raw_text="""Abstract\nThis is abstract.\n\nIntroduction\nIntro text.\n\nReferences\n[1] Ref""",
        title_guess="Title",
        abstract_guess="This is abstract.",
        section_hints=["Abstract", "Introduction", "References"],
        extractor_name="simple-text",
    )
    normalized = BasicTextNormalizer().normalize(extracted)

    assert "Abstract" in normalized.sections
    assert normalized.references_detected is True
