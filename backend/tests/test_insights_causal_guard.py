import pytest

from instamart_engine.insights.causal_guard import contains_causal_overclaim

pytestmark = pytest.mark.p0_adversarial


def test_flags_common_causal_phrases() -> None:
    assert contains_causal_overclaim("Missing freshness info causes users to abandon carts.")
    assert contains_causal_overclaim("This delay leads to lower repeat orders.")


def test_does_not_flag_associative_language() -> None:
    text = "This pattern is associated with lower repeat orders in the reviewed excerpts."
    assert contains_causal_overclaim(text) is False


def test_empty_text_is_not_flagged() -> None:
    assert contains_causal_overclaim("") is False
