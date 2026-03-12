"""Smart extractor: pypdf first, DocStruct OCR only for scanned PDFs.

Quality scoring uses five signals to decide whether pypdf text is
sufficient, avoiding expensive OCR on text-based PDFs:

  1. chars_per_page     — raw characters extracted divided by page count
  2. nonwhitespace_ratio — fraction of non-whitespace chars
  3. printable_ratio     — fraction of ASCII-printable chars (OCR noise check)
  4. academic_keywords   — presence of section headings common in papers
  5. page_yield          — fraction of pages that returned non-empty text
"""

from __future__ import annotations

import logging
import string
from pathlib import Path

from paper_farm.models.artifacts import ExtractedArtifact

log = logging.getLogger(__name__)

# Each signal contributes to a 0-100 score; threshold to skip OCR.
_SCORE_THRESHOLD = 60

_ACADEMIC_KEYWORDS = {
    "abstract", "introduction", "related work", "methodology",
    "method", "experiment", "evaluation", "results", "conclusion",
    "discussion", "references", "acknowledgment", "appendix",
}

_PRINTABLE = set(string.printable)


def _score_pypdf(pages_text: list[str], page_count: int) -> tuple[int, dict]:
    """Return (score 0-100, signal breakdown dict) for pypdf output quality."""
    total_chars = sum(len(t) for t in pages_text)
    nonempty_pages = sum(1 for t in pages_text if t.strip())
    all_text = "\n".join(pages_text)
    nonws = sum(1 for c in all_text if not c.isspace())
    printable = sum(1 for c in all_text if c in _PRINTABLE)
    lower = all_text.lower()

    # 1. chars per page  (≥300 → full score)
    cpp = total_chars / max(page_count, 1)
    s_cpp = min(cpp / 300, 1.0) * 30

    # 2. non-whitespace ratio  (≥0.5 → full score)
    nws_ratio = nonws / max(total_chars, 1)
    s_nws = min(nws_ratio / 0.5, 1.0) * 20

    # 3. printable ratio  (≥0.97 → full score; OCR noise shows as ~0.7-0.9)
    pct_ratio = printable / max(total_chars, 1)
    s_pct = min((pct_ratio - 0.5) / 0.47, 1.0) * 20   # 0 at ≤0.5, full at ≥0.97

    # 4. academic keyword hits  (≥4 distinct → full score)
    hits = sum(1 for kw in _ACADEMIC_KEYWORDS if kw in lower)
    s_kw = min(hits / 4, 1.0) * 20

    # 5. page yield  (≥0.8 pages with text → full score)
    yield_ratio = nonempty_pages / max(page_count, 1)
    s_yield = min(yield_ratio / 0.8, 1.0) * 10

    score = int(s_cpp + s_nws + s_pct + s_kw + s_yield)

    signals = {
        "total_chars":       total_chars,
        "page_count":        page_count,
        "chars_per_page":    round(cpp, 1),
        "nonws_ratio":       round(nws_ratio, 3),
        "printable_ratio":   round(pct_ratio, 3),
        "academic_kw_hits":  hits,
        "page_yield":        round(yield_ratio, 3),
        "score":             score,
        "threshold":         _SCORE_THRESHOLD,
    }
    return score, signals


class SmartExtractor:
    """Try pypdf first; fall back to DocStruct OCR only for scanned PDFs.

    All five quality signals are logged at DEBUG level so you can tune
    _SCORE_THRESHOLD without touching the code.
    """

    def __init__(self) -> None:
        # Lazy imports to avoid circular dependency
        from paper_farm.extractors.simple_text import SimpleTextExtractor
        from paper_farm.extractors.docstruct_stub import DocStructExtractor
        self._simple = SimpleTextExtractor()
        self._ocr    = DocStructExtractor()

    def extract(self, pdf_path: Path) -> ExtractedArtifact:
        pages_text, page_count = self._pypdf_pages(pdf_path)
        score, signals = _score_pypdf(pages_text, page_count)

        log.debug(
            "pypdf quality score=%d/%d  cpp=%.0f  nws=%.2f  pct=%.2f  kw=%d  yield=%.2f  file=%s",
            signals["score"], signals["threshold"],
            signals["chars_per_page"], signals["nonws_ratio"],
            signals["printable_ratio"], signals["academic_kw_hits"],
            signals["page_yield"], pdf_path.name,
        )

        if score >= _SCORE_THRESHOLD:
            log.info("pypdf OK (score=%d)  %s", score, pdf_path.name)
            raw_text = "\n\n".join(pages_text)
            return self._simple.extract(pdf_path)  # reuse post-processing logic

        log.info(
            "pypdf quality too low (score=%d < %d) — using DocStruct OCR  %s",
            score, _SCORE_THRESHOLD, pdf_path.name,
        )
        return self._ocr.extract(pdf_path)

    @staticmethod
    def _pypdf_pages(pdf_path: Path) -> tuple[list[str], int]:
        """Return (per-page text list, page count). Empty list on failure."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return pages, len(reader.pages)
        except Exception as exc:
            log.debug("pypdf failed: %s", exc)
            return [], 0
