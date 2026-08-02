"""Text normalization. architecture.md §11.1; edgecases.md NRM-*.

Normalization must not rewrite user meaning — it only repairs encoding and
collapses incidental whitespace. The original text is never touched; this
module only produces the derived `normalized_text` value.
"""

import re
import unicodedata

NORMALIZATION_VERSION = "v1"

# NRM-012 — strip unsafe control characters (keep \n and \t).
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# NRM-001 — collapse repeated spaces/tabs within a line.
_MULTI_SPACE_PATTERN = re.compile(r"[ \t]{2,}")
# NRM-008 — collapse excessive blank lines but preserve paragraph breaks.
_MULTI_BLANK_LINE_PATTERN = re.compile(r"\n{3,}")


def normalize_text(text: str | None) -> str:
    if not text:
        return ""

    # NRM-009 — NFC normalization; the version above lets a future change be
    # tracked as a new normalized representation rather than a silent edit.
    normalized = unicodedata.normalize("NFC", text)
    normalized = _CONTROL_CHAR_PATTERN.sub("", normalized)
    normalized = _MULTI_SPACE_PATTERN.sub(" ", normalized)
    normalized = _MULTI_BLANK_LINE_PATTERN.sub("\n\n", normalized)
    return normalized.strip()
