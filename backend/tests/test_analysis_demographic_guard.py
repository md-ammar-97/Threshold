import pytest

from instamart_engine.analysis.demographic_guard import contains_demographic_inference

pytestmark = pytest.mark.p0_adversarial


def test_flags_common_demographic_phrases() -> None:
    assert contains_demographic_inference("This is likely a young professional user.")
    assert contains_demographic_inference("Sounds like a working mother short on time.")


def test_does_not_flag_ordinary_summary() -> None:
    text = "User complained about a delayed order and requested a refund."
    assert contains_demographic_inference(text) is False


def test_empty_text_is_not_flagged() -> None:
    assert contains_demographic_inference("") is False
