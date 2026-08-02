"""Deduplication. architecture.md §11.5; edgecases.md Part II §15 (DUP-*).

Two levels, both deterministic for Phase 1:
1. Exact — content_hash equality (sha256 of normalized text).
2. Near-duplicate — lexical (token-set Jaccard) similarity against a bounded
   candidate set. Embedding-based semantic near-duplicate detection is
   Phase 3 scope (needs the embedding pipeline); this is the lexical
   fallback architecture.md §14.4/EMB-012 already anticipates.
"""

import hashlib
import re
from uuid import UUID

NEAR_DUPLICATE_THRESHOLD = 0.85
DEDUP_DECISION_VERSION = "lexical-jaccard-v1"
# DUP-004 — don't call two short generic reviews duplicates just because
# they're lexically identical; require enough content to be meaningful.
MIN_LENGTH_FOR_NEAR_DUP_CHECK = 20

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def compute_content_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


def jaccard_similarity(a: str, b: str) -> float:
    tokens_a, tokens_b = _tokenize(a), _tokenize(b)
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def find_near_duplicate(
    normalized_text: str, candidates: list[tuple[UUID, str]]
) -> tuple[UUID, float] | None:
    if len(normalized_text.strip()) < MIN_LENGTH_FOR_NEAR_DUP_CHECK:
        return None

    best: tuple[UUID, float] | None = None
    for candidate_id, candidate_text in candidates:
        score = jaccard_similarity(normalized_text, candidate_text)
        if score >= NEAR_DUPLICATE_THRESHOLD and (best is None or score > best[1]):
            best = (candidate_id, score)
    return best
