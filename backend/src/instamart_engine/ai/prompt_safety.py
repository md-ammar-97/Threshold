"""Delimiting untrusted content in prompts. edgecases.md AISEC-004/005/008.

Every task's system prompt must separately instruct the model not to follow
instructions found inside source content (architecture.md §12.4) — this
module is the gateway-level second layer: it wraps untrusted text in an
unambiguous, clearly-labelled boundary so injected "ignore previous
instructions"-style content is visibly data, not conversation structure,
regardless of which prompt template is in use.
"""

_OPEN_TAG = "<untrusted_user_feedback>"
_CLOSE_TAG = "</untrusted_user_feedback>"


def delimit_untrusted_content(text: str) -> str:
    # AISEC-004 — strip any literal occurrences of the boundary tags from
    # the untrusted text itself so it cannot forge a fake closing boundary.
    sanitized = text.replace(_OPEN_TAG, "").replace(_CLOSE_TAG, "")
    return f"{_OPEN_TAG}\n{sanitized}\n{_CLOSE_TAG}"
