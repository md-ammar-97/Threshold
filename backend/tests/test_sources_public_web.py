"""Unit tests for the public web connector. Uses httpx.MockTransport — no
real network access."""

import httpx
import pytest

from instamart_engine.sources.base import CollectionRequest, SourceConfig
from instamart_engine.sources.exceptions import SourceBlockedContentError, SourceConfigError
from instamart_engine.sources.public_web import PublicWebConnector

SAMPLE_HTML = """
<html>
<head><title>Sample Article</title><meta name="author" content="A. Writer"></head>
<body>
<article>
<h1>Why quick commerce shoppers stick to known categories</h1>
<p>Users repeatedly buy from the same categories because it is fast and predictable.
They rarely explore new product categories unless a discount is prominently shown.
This pattern repeats across many quick-commerce apps in India today.</p>
</article>
</body>
</html>
"""


def _client_for(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_validate_config_requires_at_least_one_url() -> None:
    connector = PublicWebConnector(client=_client_for(lambda r: httpx.Response(200)))
    with pytest.raises(SourceConfigError):
        connector.validate_config(SourceConfig(target_identifier=""))


def test_collect_extracts_passage_from_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SAMPLE_HTML, headers={"content-type": "text/html"})

    connector = PublicWebConnector(client=_client_for(handler))
    request = CollectionRequest(
        config=SourceConfig(target_identifier="https://example.com/quick-commerce-habits")
    )

    items = list(connector.collect(request))

    assert len(items) == 1
    item = items[0]
    assert item.record_type == "article_passage"
    assert item.body is not None
    assert "quick commerce" in item.body.lower() or "quick-commerce" in item.body.lower()
    assert item.source_url == "https://example.com/quick-commerce-habits"

    checkpoint = connector.checkpoint()
    assert checkpoint is not None
    assert checkpoint.is_terminal is True


def test_collect_handles_empty_page_without_dropping_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<html><body></body></html>", headers={"content-type": "text/html"}
        )

    connector = PublicWebConnector(client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="https://example.com/empty"))

    items = list(connector.collect(request))

    assert len(items) == 1  # still yielded — relevance decision belongs downstream
    assert items[0].source_metadata["extraction_status"] in {"empty", "no_extractable_content"}


def test_collect_raises_on_challenge_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='<html><body><div class="g-recaptcha"></div></body></html>',
            headers={"content-type": "text/html"},
        )

    connector = PublicWebConnector(client=_client_for(handler))
    request = CollectionRequest(config=SourceConfig(target_identifier="https://example.com/blocked"))

    with pytest.raises(SourceBlockedContentError):
        list(connector.collect(request))


def test_ssrf_blocked_url_is_rejected_before_any_request() -> None:
    connector = PublicWebConnector(client=_client_for(lambda r: httpx.Response(200)))
    request = CollectionRequest(config=SourceConfig(target_identifier="http://127.0.0.1:8000/admin"))

    with pytest.raises(SourceConfigError):
        list(connector.collect(request))
