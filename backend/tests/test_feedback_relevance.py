from instamart_engine.feedback.models import QualityStatus, RelevanceStatus
from instamart_engine.feedback.relevance import assess_quality, assess_relevance


def test_empty_text_is_insufficient_content() -> None:
    assert assess_relevance("") == RelevanceStatus.INSUFFICIENT_CONTENT
    assert assess_relevance("   ") == RelevanceStatus.INSUFFICIENT_CONTENT


def test_url_only_text_is_insufficient_content() -> None:
    assert assess_relevance("https://example.com/promo") == RelevanceStatus.INSUFFICIENT_CONTENT


def test_obvious_spam_marker_is_flagged() -> None:
    assert (
        assess_relevance("Click here to win a free iPhone now!!! click here to win big")
        == RelevanceStatus.SPAM_OR_PROMOTION
    )


def test_ordinary_feedback_is_left_unreviewed_for_phase_2() -> None:
    text = "The app is convenient but I wish there were more product categories to explore."
    assert assess_relevance(text) == RelevanceStatus.UNREVIEWED


def test_quality_malformed_when_normalization_erases_nonempty_text() -> None:
    status = assess_quality(
        original_text="\x00\x01\x02",
        normalized_text="",
        language_code=None,
        is_code_mixed=False,
        is_supported_language=True,
    )
    assert status == QualityStatus.MALFORMED


def test_quality_unsupported_language_only_when_confirmed_not_just_unknown() -> None:
    status = assess_quality(
        original_text="a long enough french sentence about delivery",
        normalized_text="a long enough french sentence about delivery",
        language_code="fr",
        is_code_mixed=False,
        is_supported_language=False,
    )
    assert status == QualityStatus.UNSUPPORTED_LANGUAGE


def test_quality_short_text_with_unknown_language_is_low_information_not_unsupported() -> None:
    """A short English review like "good" has no confirmed language (too
    short to detect) — it must not be mislabelled unsupported_language."""
    status = assess_quality(
        original_text="good",
        normalized_text="good",
        language_code=None,
        is_code_mixed=False,
        is_supported_language=False,
    )
    assert status == QualityStatus.LOW_INFORMATION


def test_quality_low_information_for_short_supported_text() -> None:
    status = assess_quality(
        original_text="good",
        normalized_text="good",
        language_code="en",
        is_code_mixed=False,
        is_supported_language=True,
    )
    assert status == QualityStatus.LOW_INFORMATION


def test_quality_usable_for_normal_feedback() -> None:
    text = "The delivery was fast and packaging was good this time."
    status = assess_quality(
        original_text=text,
        normalized_text=text,
        language_code="en",
        is_code_mixed=False,
        is_supported_language=True,
    )
    assert status == QualityStatus.USABLE
