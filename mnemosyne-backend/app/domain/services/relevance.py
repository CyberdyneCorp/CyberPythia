"""Lexical relevance scoring for issues, PRs, OpenSpec changes, and files (design D8).

Deterministic keyword scoring — no LLM. Semantic search covers documents;
this covers everything that isn't embedded.
"""

import re

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "in", "is", "it", "of", "on", "or", "the", "to", "want", "we",
    "what", "when", "where", "which", "who", "will", "with", "you",
}  # fmt: skip

_TOKEN = re.compile(r"[a-z0-9_+-]{2,}")


def tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}


def keyword_score(
    query: str, *fields: str | None, weights: tuple[float, ...] | None = None
) -> float:
    """Weighted fraction of query terms found in each field (0..1)."""
    terms = tokenize(query)
    if not terms:
        return 0.0
    if weights is None:
        weights = tuple(1.0 for _ in fields)
    total_weight = sum(weights) or 1.0
    score = 0.0
    for field, weight in zip(fields, weights, strict=True):
        if not field:
            continue
        field_tokens = tokenize(field)
        overlap = len(terms & field_tokens) / len(terms)
        score += weight * overlap
    return min(1.0, score / total_weight)
