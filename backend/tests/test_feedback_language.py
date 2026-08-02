from instamart_engine.feedback.language import detect_language


def test_short_text_is_not_trusted() -> None:
    result = detect_language("ok")
    assert result.language_code is None
    assert result.is_supported is False


def test_english_text_is_detected_and_supported() -> None:
    result = detect_language(
        "The delivery was fast and the app is easy to use for everyday grocery shopping."
    )
    assert result.language_code == "en"
    assert result.is_supported is True
    assert result.is_code_mixed is False


def test_code_mixed_english_hindi_is_supported() -> None:
    result = detect_language("यह app बहुत अच्छा है aur delivery bhi fast hai roz milta hai")
    assert result.is_code_mixed is True
    assert result.is_supported is True


def test_unsupported_language_is_marked_not_supported() -> None:
    result = detect_language(
        "Ceci est un commentaire assez long en français sur une application de livraison."
    )
    assert result.is_supported is False
    assert result.is_code_mixed is False
