"""Deterministic PII redaction. architecture.md §11.3; edgecases.md PII-*.

Rule-based only for Phase 1 (email, phone, order-id-like, UPI-like payment
identifiers). Person-name and address detection need an ML/NER approach and
are explicitly deferred — see the module docstring in `relevance.py` for the
same "deterministic first" philosophy (architecture.md §11.4).

The original sensitive substring is never returned — only redacted text and
structured redaction events describing what was removed (datamodel.md §15).
"""

import re
from dataclasses import dataclass

REDACTION_DETECTOR_VERSION = "rule-v1"

_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# UPI-style handles (name@bankhandle) look like emails but the part after
# `@` has no dot — checked only where the email pattern didn't already match.
_UPI_PATTERN = re.compile(r"\b[\w.\-]{2,}@[a-zA-Z]{2,15}\b")
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)")
_ORDER_ID_PATTERN = re.compile(
    r"\border\s*(?:id|no\.?|number)?\s*[:#-]?\s*([A-Z0-9]{6,20})\b", re.IGNORECASE
)

_REPLACEMENT_TOKENS = {
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "payment_identifier": "[PAYMENT_ID]",
    "order_id": "[ORDER_ID]",
}


@dataclass(frozen=True, slots=True)
class RedactionEvent:
    redaction_type: str
    start_offset: int
    end_offset: int
    replacement_token: str
    confidence: float


def redact(text: str) -> tuple[str, list[RedactionEvent]]:
    if not text:
        return text or "", []

    candidates: list[tuple[int, int, str, float]] = []

    for m in _EMAIL_PATTERN.finditer(text):
        candidates.append((m.start(), m.end(), "email", 0.95))

    for m in _PHONE_PATTERN.finditer(text):
        candidates.append((m.start(), m.end(), "phone", 0.9))

    for m in _ORDER_ID_PATTERN.finditer(text):
        candidates.append((m.start(1), m.end(1), "order_id", 0.6))

    email_spans = [(s, e) for s, e, t, _ in candidates if t == "email"]
    for m in _UPI_PATTERN.finditer(text):
        if any(s <= m.start() < e for s, e in email_spans):
            continue
        candidates.append((m.start(), m.end(), "payment_identifier", 0.7))

    # Resolve overlaps: prefer higher confidence, then earliest start.
    candidates.sort(key=lambda c: (-c[3], c[0]))
    selected: list[tuple[int, int, str, float]] = []
    for cand in candidates:
        if any(not (cand[1] <= s[0] or cand[0] >= s[1]) for s in selected):
            continue
        selected.append(cand)
    selected.sort(key=lambda c: c[0])

    events = [
        RedactionEvent(
            redaction_type=redaction_type,
            start_offset=start,
            end_offset=end,
            replacement_token=_REPLACEMENT_TOKENS[redaction_type],
            confidence=confidence,
        )
        for start, end, redaction_type, confidence in selected
    ]

    redacted = text
    for start, end, redaction_type, _confidence in sorted(
        selected, key=lambda c: c[0], reverse=True
    ):
        redacted = redacted[:start] + _REPLACEMENT_TOKENS[redaction_type] + redacted[end:]

    return redacted, events
