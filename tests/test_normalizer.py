from paper_farm.normalizers import BasicTextNormalizer


def test_normalizer_to_paper_struct_keeps_abstract_and_sections() -> None:
    text = (
        "Abstract\n"
        "This paper proposes a new method.\n\n"
        "Introduction\n"
        "We tackle routing problems.\n\n"
        "Method\n"
        "Our model is lightweight.\n"
    )
    paper = BasicTextNormalizer().to_paper_struct("Paper Title", text)

    assert paper.title == "Paper Title"
    assert "proposes" in paper.abstract
    assert any(section.name == "Introduction" for section in paper.sections)
    assert any(section.name == "Method" for section in paper.sections)
