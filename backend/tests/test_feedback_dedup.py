import uuid

from instamart_engine.feedback.dedup import (
    compute_content_hash,
    find_near_duplicate,
    jaccard_similarity,
)


def test_content_hash_is_deterministic_and_sensitive_to_change() -> None:
    a = compute_content_hash("the app is great")
    b = compute_content_hash("the app is great")
    c = compute_content_hash("the app is terrible")
    assert a == b
    assert a != c


def test_jaccard_similarity_identical_text_is_one() -> None:
    assert jaccard_similarity("fast delivery great app", "fast delivery great app") == 1.0


def test_jaccard_similarity_unrelated_text_is_low() -> None:
    score = jaccard_similarity("fast delivery great app", "completely different words here")
    assert score < 0.3


def test_find_near_duplicate_matches_above_threshold() -> None:
    target_id = uuid.uuid4()
    original = (
        "the quick commerce app has fast delivery and reliable packaging "
        "with helpful customer support every single time i order"
    )
    near_copy = (
        "the quick commerce app has fast delivery and reliable packaging "
        "with helpful customer support almost every single time i order"
    )
    candidates = [
        (target_id, original),
        (uuid.uuid4(), "totally unrelated text about something else entirely"),
    ]
    result = find_near_duplicate(near_copy, candidates)
    assert result is not None
    assert result[0] == target_id


def test_find_near_duplicate_ignores_short_generic_text() -> None:
    """DUP-004 — short generic reviews shouldn't be matched purely by luck."""
    candidates = [(uuid.uuid4(), "good")]
    assert find_near_duplicate("nice", candidates) is None


def test_find_near_duplicate_returns_none_when_no_match() -> None:
    candidates = [(uuid.uuid4(), "a completely unrelated long piece of text about weather")]
    result = find_near_duplicate(
        "the quick commerce app has fast delivery and great packaging", candidates
    )
    assert result is None
