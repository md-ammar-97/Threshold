"""Language detection. context.md §6/§11.2; edgecases.md LNG-*.

English and English-Hindi code-mixed content are the two supported cases
for the MVP (context.md §20). Everything else is retained and marked
`unsupported_language`, never discarded (architecture.md §11.2).
"""

import re
from dataclasses import dataclass

from langdetect import DetectorFactory, LangDetectException, detect_langs

# langdetect's detection is non-deterministic across runs unless seeded.
DetectorFactory.seed = 0

LANGUAGE_DETECTION_VERSION = "langdetect-v1"
SUPPORTED_LANGUAGES = {"en", "hi"}
# LNG-005 — emojis/product names dominate short strings; don't trust the
# detector below this length.
MIN_TEXT_LENGTH_FOR_DETECTION = 12

_DEVANAGARI_PATTERN = re.compile(r"[ऀ-ॿ]")
_LATIN_WORD_PATTERN = re.compile(r"[A-Za-z]{2,}")


@dataclass(frozen=True, slots=True)
class LanguageResult:
    language_code: str | None
    confidence: float | None
    is_code_mixed: bool
    is_supported: bool


def detect_language(text: str) -> LanguageResult:
    if not text or len(text.strip()) < MIN_TEXT_LENGTH_FOR_DETECTION:
        return LanguageResult(
            language_code=None, confidence=None, is_code_mixed=False, is_supported=False
        )

    has_devanagari = bool(_DEVANAGARI_PATTERN.search(text))
    has_latin_words = bool(_LATIN_WORD_PATTERN.search(text))
    is_code_mixed = has_devanagari and has_latin_words  # LNG-003

    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return LanguageResult(
            language_code=None,
            confidence=None,
            is_code_mixed=is_code_mixed,
            is_supported=is_code_mixed,
        )

    if not candidates:
        return LanguageResult(
            language_code=None,
            confidence=None,
            is_code_mixed=is_code_mixed,
            is_supported=is_code_mixed,
        )

    top = candidates[0]
    language_code = top.lang
    confidence = float(top.prob)
    is_supported = is_code_mixed or language_code in SUPPORTED_LANGUAGES

    return LanguageResult(
        language_code=language_code,
        confidence=confidence,
        is_code_mixed=is_code_mixed,
        is_supported=is_supported,
    )
