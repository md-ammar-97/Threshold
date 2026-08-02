"""Deterministic backstop against causal overclaiming. edgecases.md INS-002;
ai_evals.md §32.2/§33 "causal phrase detector".

The system prompt already instructs the model to describe association, not
proven causation, from public feedback. This is the second layer: a narrow
keyword scan over free-text output fields, mirroring
`analysis.demographic_guard`'s approach to the analogous demographic-inference
risk.
"""

_CAUSAL_MARKERS = (
    "causes",
    "caused by",
    "causing",
    "leads to",
    "leading to",
    "led to",
    "results in",
    "resulting in",
    "resulted in",
    "is the reason",
    "is why users",
    "drives users to",
    "makes users",
    "forces users to",
    "as a direct result of",
)


def contains_causal_overclaim(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _CAUSAL_MARKERS)
