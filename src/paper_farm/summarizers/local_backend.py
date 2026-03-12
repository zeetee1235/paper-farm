"""Local deterministic summarizer producing output_contract schema."""

import re

from paper_farm.models.artifacts import PaperStruct, SummaryResult


class LocalSummaryBackend:
    """Rule-based summary backend with Korean narrative output."""

    def summarize(self, paper: PaperStruct) -> SummaryResult:
        abstract = paper.abstract
        full_text = "\n".join(section.content for section in paper.sections)
        method_text = self._match_sentences(full_text, ["method", "approach", "model", "architecture"], 2)
        result_text = self._match_sentences(full_text, ["result", "improv", "accuracy", "evaluation"], 2)
        limitation_text = self._match_sentences(full_text, ["limitation", "future work", "however", "weakness"], 2)

        summary = self._ko_summary(abstract, full_text)
        contributions = self._contributions(abstract, full_text)
        method = self._join_or_uncertain(method_text, "Could not identify method sentences with sufficient clarity.")
        results = self._join_or_uncertain(result_text, "Could not identify result sentences with sufficient clarity.")
        limitations = self._join_or_uncertain(
            limitation_text,
            "Limitations are not explicitly stated in the text.",
        )
        keywords = self._keywords(abstract + "\n" + full_text)

        obsidian_markdown = self._build_markdown(
            title=paper.title,
            summary=summary,
            contributions=contributions,
            method=method,
            results=results,
            limitations=limitations,
            keywords=keywords,
        )

        return SummaryResult(
            title=paper.title,
            summary=summary,
            contributions=contributions,
            method=method,
            results=results,
            limitations=limitations,
            keywords=keywords,
            obsidian_markdown=obsidian_markdown,
        )

    def _ko_summary(self, abstract: str, full_text: str) -> str:
        source = abstract or full_text
        sentence = self._first_sentence(source)
        if sentence:
            return sentence
        return "Insufficient abstract/body text to generate a reliable summary."

    def _contributions(self, abstract: str, full_text: str) -> list[str]:
        source = abstract or full_text
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", source) if len(s.strip()) > 20]
        if not sentences:
            return ["Insufficient sentences to extract contributions."]
        items = sentences[:3]
        return [f"{idx + 1}. {sent}" for idx, sent in enumerate(items)]

    def _build_markdown(
        self,
        *,
        title: str,
        summary: str,
        contributions: list[str],
        method: str,
        results: str,
        limitations: str,
        keywords: list[str],
    ) -> str:
        keyword_line = ", ".join(keywords)
        contribution_lines = "\n".join(f"- {c}" for c in contributions)
        return (
            f"# {title}\n\n"
            "## Summary\n"
            f"{summary}\n\n"
            "## Contributions\n"
            f"{contribution_lines}\n\n"
            "## Method\n"
            f"{method}\n\n"
            "## Results\n"
            f"{results}\n\n"
            "## Limitations\n"
            f"{limitations}\n\n"
            "## Keywords\n"
            f"{keyword_line}\n"
        )

    @staticmethod
    def _first_sentence(text: str) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        if not parts or not parts[0]:
            return ""
        return parts[0][:240]

    @staticmethod
    def _match_sentences(text: str, terms: list[str], limit: int) -> list[str]:
        matched: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            low = sentence.lower()
            if any(term in low for term in terms):
                cleaned = sentence.strip()
                if cleaned:
                    matched.append(cleaned[:300])
            if len(matched) >= limit:
                break
        return matched

    @staticmethod
    def _join_or_uncertain(sentences: list[str], fallback: str) -> str:
        return " ".join(sentences) if sentences else fallback

    @staticmethod
    def _keywords(text: str) -> list[str]:
        stop = {
            "the",
            "and",
            "for",
            "with",
            "that",
            "from",
            "this",
            "into",
            "using",
            "based",
            "their",
            "have",
            "been",
            "were",
        }
        words = re.findall(r"[A-Za-z]{4,}", text)
        freq: dict[str, int] = {}
        for word in words:
            lower = word.lower()
            if lower in stop:
                continue
            freq[lower] = freq.get(lower, 0) + 1
        ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        return [word for word, _ in ranked[:8]]
