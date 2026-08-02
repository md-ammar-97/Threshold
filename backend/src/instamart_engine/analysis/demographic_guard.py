"""Deterministic backstop against demographic inference. edgecases.md CLS-017.

The system prompt already instructs the model never to infer age, gender,
income, occupation, or household attributes (context.md §7.D). This is the
second layer: a keyword scan over free-text output fields (`summary` and
label evidence excerpts) that would only match if the model violated that
instruction. It is deliberately narrow — a small, high-precision marker
list — rather than a general demographic-inference classifier, which is
out of scope for Phase 2.
"""

_DEMOGRAPHIC_MARKERS = (
    "young professional",
    "elderly",
    "housewife",
    "middle-aged",
    "male user",
    "female user",
    "high-income",
    "low-income",
    "student budget",
    "working mother",
    "working father",
    "teenage",
    "in his 20s",
    "in her 20s",
    "in his 30s",
    "in her 30s",
    "in his 40s",
    "in her 40s",
    "senior citizen",
    "bachelor lifestyle",
)


def contains_demographic_inference(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _DEMOGRAPHIC_MARKERS)
