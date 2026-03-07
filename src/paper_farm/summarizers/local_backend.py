"""Deterministic local summary backend for MVP."""

import re
from pathlib import Path

from paper_farm.models.artifacts import CleanedArtifact, SummaryResult


class LocalSummaryBackend:
    """Rule-based summary generator with stable JSON schema."""

    mode = "local"

    def summarize(self, paper_id: str, cleaned: CleanedArtifact, paper_dir: Path) -> SummaryResult:
        del paper_id, paper_dir
        abstract = cleaned.sections.get("Abstract", "")
        intro = cleaned.sections.get("Introduction", "")
        conclusion = cleaned.sections.get("Conclusion", "")
        body = cleaned.cleaned_text

        one_line = self._first_sentence(abstract) or self._first_sentence(intro) or "Paper summary unavailable."
        short_summary = " ".join(x for x in [abstract[:500], intro[:300], conclusion[:300]] if x).strip()[:1000]
        if not short_summary:
            short_summary = body[:1000]

        contributions = self._bullet_candidates(abstract + "\n" + intro, limit=3)
        methods = self._match_sentences(body, ["method", "approach", "model", "architecture"], limit=3)
        experiments = self._match_sentences(body, ["experiment", "dataset", "benchmark", "evaluation"], limit=3)
        limitations = self._match_sentences(body, ["limitation", "future work", "weakness", "however"], limit=3)
        keywords = self._keywords(body)

        return SummaryResult(
            mode=self.mode,
            one_line=one_line,
            short_summary=short_summary,
            contributions=contributions or ["Contribution extraction heuristic returned no candidates."],
            methods=methods or ["Method extraction heuristic returned no candidates."],
            experiments=experiments or ["Experiment extraction heuristic returned no candidates."],
            limitations=limitations or ["No explicit limitations detected by heuristic."],
            keywords=keywords,
        )

    @staticmethod
    def _first_sentence(text: str) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return parts[0][:240] if parts and parts[0] else ""

    @staticmethod
    def _bullet_candidates(text: str, limit: int) -> list[str]:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 30]
        return sentences[:limit]

    @staticmethod
    def _match_sentences(text: str, terms: list[str], limit: int) -> list[str]:
        out: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if any(term in sentence.lower() for term in terms):
                cleaned = sentence.strip()
                if len(cleaned) > 20:
                    out.append(cleaned[:240])
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _keywords(text: str) -> list[str]:
        stop = {"the", "and", "for", "with", "that", "from", "this", "are", "was", "were", "into", "their"}
        words = re.findall(r"[a-zA-Z]{5,}", text.lower())
        freq: dict[str, int] = {}
        for word in words:
            if word in stop:
                continue
            freq[word] = freq.get(word, 0) + 1
        ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        return [w for w, _ in ranked[:8]]
