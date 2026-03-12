from paper_farm.models.artifacts import PaperSection, PaperStruct
from paper_farm.summarizers.local_backend import LocalSummaryBackend


def test_local_summary_matches_output_contract_shape() -> None:
    paper = PaperStruct(
        title="Sample Paper",
        abstract="This paper proposes a compact model for sensor routing.",
        sections=[
            PaperSection(name="Method", content="Our method uses a graph-based model."),
            PaperSection(name="Results", content="Results show improved accuracy over baselines."),
        ],
    )

    summary = LocalSummaryBackend().summarize(paper)

    assert summary.title == "Sample Paper"
    assert isinstance(summary.summary, str)
    assert isinstance(summary.contributions, list)
    assert isinstance(summary.method, str)
    assert isinstance(summary.results, str)
    assert isinstance(summary.limitations, str)
    assert isinstance(summary.keywords, list)
    assert isinstance(summary.obsidian_markdown, str)
