"""Small pure-Python fuzzy matcher for bookmark search.

No third-party dependency (keeps the project's minimal deps). Scoring favors, in
order: exact substring matches (earlier + at a word boundary rank higher), then
subsequence matches (all query characters appear in order, contiguous runs and
word-boundary starts rewarded). Returns None for non-matches.

Typical use::

    ranked = fuzzy_search(query, bookmarks, key=lambda b: (b.title, b.url))
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple, TypeVar

T = TypeVar("T")

_WORD_BOUNDARY = " /-_.:|>\t"


def fuzzy_score(query: str, text: str) -> Optional[float]:
    """Score how well ``query`` matches ``text``. Higher is better; None means no
    match. Case-insensitive."""
    if not query:
        return 0.0
    if not text:
        return None
    q = query.lower()
    t = text.lower()

    idx = t.find(q)
    if idx != -1:
        score = 100.0
        if idx == 0:
            score += 40.0  # prefix match
        elif t[idx - 1] in _WORD_BOUNDARY:
            score += 25.0  # word-boundary match
        score -= min(20.0, idx * 0.5)          # earlier is better
        score -= min(15.0, (len(t) - len(q)) * 0.2)  # tighter is better
        return score

    return _subsequence_score(q, t)


def _subsequence_score(q: str, t: str) -> Optional[float]:
    """Score ``q`` as an ordered subsequence of ``t`` (fzf-style). None if not a
    subsequence."""
    score = 0.0
    ti = 0
    run = 0
    matched = 0
    for qc in q:
        found = t.find(qc, ti)
        if found == -1:
            return None
        matched += 1
        if found == ti and ti > 0:
            run += 1
            score += 5.0 + run * 2.0  # reward contiguous runs
        else:
            run = 0
            score += 1.0
        if found == 0 or t[found - 1] in _WORD_BOUNDARY:
            score += 8.0  # matched at a word boundary
        ti = found + 1
    # Normalize so subsequence hits stay below substring hits, and denser matches
    # (query covers more of the text) rank higher.
    density = matched / len(t)
    return min(90.0, score + density * 10.0)


def fuzzy_search(
    query: str,
    items: List[T],
    key: Callable[[T], Tuple[str, ...]],
    *,
    weights: Optional[Tuple[float, ...]] = None,
) -> List[Tuple[T, float]]:
    """Rank ``items`` against ``query``. ``key`` returns the searchable fields for
    an item (e.g. (title, url)); ``weights`` scales each field's score (defaults
    to 1.0 for the first field and 0.6 for the rest, so title beats url). An item
    matches if any field matches; its score is the best weighted field score.
    Returns (item, score) sorted best-first; non-matches are dropped."""
    results: List[Tuple[T, float]] = []
    for item in items:
        fields = key(item)
        if weights is None:
            field_weights = tuple(1.0 if i == 0 else 0.6 for i in range(len(fields)))
        else:
            field_weights = weights
        best: Optional[float] = None
        for field, weight in zip(fields, field_weights):
            s = fuzzy_score(query, field)
            if s is None:
                continue
            weighted = s * weight
            if best is None or weighted > best:
                best = weighted
        if best is not None:
            results.append((item, best))
    results.sort(key=lambda pair: pair[1], reverse=True)
    return results
