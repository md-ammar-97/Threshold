from instamart_engine.feedback.privacy import redact


def test_redacts_email() -> None:
    redacted, events = redact("contact me at jane.doe@example.com please")
    assert "jane.doe@example.com" not in redacted
    assert "[EMAIL]" in redacted
    assert any(e.redaction_type == "email" for e in events)


def test_redacts_indian_phone_number() -> None:
    redacted, events = redact("call me on 9876543210 anytime")
    assert "9876543210" not in redacted
    assert "[PHONE]" in redacted
    assert any(e.redaction_type == "phone" for e in events)


def test_redacts_upi_style_payment_identifier_not_as_email() -> None:
    redacted, events = redact("pay me at rahul123@ybl for the refund")
    assert "rahul123@ybl" not in redacted
    assert "[PAYMENT_ID]" in redacted
    assert any(e.redaction_type == "payment_identifier" for e in events)
    assert not any(e.redaction_type == "email" for e in events)


def test_does_not_redact_ordinary_text() -> None:
    text = "The app is great and delivery was fast this time around."
    redacted, events = redact(text)
    assert redacted == text
    assert events == []


def test_empty_text_returns_empty_with_no_events() -> None:
    redacted, events = redact("")
    assert redacted == ""
    assert events == []


def test_original_sensitive_value_never_appears_in_events() -> None:
    _redacted, events = redact("email me at secret@example.com")
    for event in events:
        assert "secret@example.com" not in event.replacement_token
