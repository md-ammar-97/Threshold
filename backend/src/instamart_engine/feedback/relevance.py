"""Deterministic relevance and quality rules. architecture.md §11.4.

"Use deterministic rules first, followed by a small structured classifier
for ambiguous records." The LLM classifier is Phase 2 scope; this module
only decides the clear-cut cases (empty, URL-only, obvious spam markers)
and otherwise leaves the record `unreviewed` for later, richer
classification rather than guessing.
"""

import re

from instamart_engine.feedback.models import QualityStatus, RelevanceStatus

MIN_MEANINGFUL_LENGTH = 15

_URL_ONLY_PATTERN = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)
# REL-003 — explicit, unambiguous commercial-spam markers only; anything
# subtler is left to the Phase 2 classifier rather than guessed here.
_SPAM_MARKERS = (
    "click here to win",
    "free gift card",
    "whatsapp me at",
    "dm me for a discount code",
)


def assess_relevance(normalized_text: str) -> RelevanceStatus:
    if not normalized_text.strip():
        return RelevanceStatus.INSUFFICIENT_CONTENT
    if _URL_ONLY_PATTERN.match(normalized_text):  # REC-012
        return RelevanceStatus.INSUFFICIENT_CONTENT

    lowered = normalized_text.lower()
    if any(marker in lowered for marker in _SPAM_MARKERS):
        return RelevanceStatus.SPAM_OR_PROMOTION

    return RelevanceStatus.UNREVIEWED


def assess_quality(
    *,
    original_text: str,
    normalized_text: str,
    language_code: str | None,
    is_code_mixed: bool,
    is_supported_language: bool,
) -> QualityStatus:
    """`language_code=None` means detection was skipped or inconclusive
    (LNG-001/LNG-005 — e.g. text too short), which is a different situation
    from a *confirmed* detection of an unsupported language and must not be
    mislabelled `unsupported_language`; it falls through to the length check
    instead, which is the actually-correct reason a review like "good" is
    low-value."""
    if original_text.strip() and not normalized_text.strip():
        return QualityStatus.MALFORMED
    if language_code is not None and not is_code_mixed and not is_supported_language:
        return QualityStatus.UNSUPPORTED_LANGUAGE
    if len(normalized_text.strip()) < MIN_MEANINGFUL_LENGTH:
        return QualityStatus.LOW_INFORMATION
    return QualityStatus.USABLE
