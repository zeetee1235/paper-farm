from paper_farm.models.artifacts import CleanedArtifact
from paper_farm.summarizers.local_backend import LocalSummaryBackend


def test_local_summary_schema_has_expected_fields() -> None:
    cleaned = CleanedArtifact(
        cleaned_text="Abstract This work proposes a method. We evaluate on benchmark datasets.",
        sections={"Abstract": "This work proposes a method.", "Conclusion": "Results are promising."},
        references_detected=False,
        normalizer_name="basic-text",
    )

    summary = LocalSummaryBackend().summarize("pid", cleaned, paper_dir=__import__("pathlib").Path("."))

    assert summary.mode == "local"
    assert isinstance(summary.contributions, list)
    assert isinstance(summary.methods, list)
    assert isinstance(summary.experiments, list)
    assert isinstance(summary.limitations, list)
    assert isinstance(summary.keywords, list)
