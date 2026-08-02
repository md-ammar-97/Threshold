from instamart_engine.feedback.normalize import normalize_text


def test_normalize_collapses_whitespace_and_strips() -> None:
    assert normalize_text("  hello   world  ") == "hello world"


def test_normalize_collapses_excess_blank_lines_but_keeps_paragraphs() -> None:
    result = normalize_text("para one\n\n\n\n\npara two")
    assert result == "para one\n\npara two"


def test_normalize_strips_control_characters() -> None:
    result = normalize_text("hello\x00\x07world")
    assert result == "helloworld"


def test_normalize_handles_none_and_empty() -> None:
    assert normalize_text(None) == ""
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_normalize_preserves_code_mixed_content() -> None:
    text = "यह app बहुत अच्छा है, delivery bhi fast hai"
    result = normalize_text(text)
    assert "app" in result
    assert "delivery" in result
    assert "यह" in result
