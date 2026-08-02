"""Unit tests for the Google Play connector. Mocks the underlying library —
no network access — per edgecases.md §7 ("live connector tests should be
opt-in"). See test_sources_google_play_live.py for the opt-in live test.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from google_play_scraper.features.reviews import _ContinuationToken

from instamart_engine.sources.base import CollectionRequest, ConnectorCheckpoint, SourceConfig
from instamart_engine.sources.exceptions import SourceConfigError, SourceUnavailableError
from instamart_engine.sources.google_play import GooglePlayConnector

SAMPLE_REVIEW = {
    "reviewId": "abc-123",
    "userName": "Jane Doe",
    "userImage": "https://example.com/avatar.png",
    "content": "Great app, fast delivery!",
    "score": 5,
    "thumbsUpCount": 3,
    "reviewCreatedVersion": "4.100.0",
    "at": datetime(2026, 6, 1, 10, 30, 0),
    "replyContent": None,
    "repliedAt": None,
    "appVersion": "4.100.0",
}


def test_validate_config_rejects_non_package_id() -> None:
    connector = GooglePlayConnector()
    with pytest.raises(SourceConfigError):
        connector.validate_config(SourceConfig(target_identifier="not a package id"))


def test_collect_yields_mapped_items_and_sets_terminal_checkpoint() -> None:
    connector = GooglePlayConnector(lang="en", country="in")
    terminal_token = _ContinuationToken(None, "en", "in", 2, 200, None, None)

    with patch(
        "instamart_engine.sources.google_play.gp_reviews",
        return_value=([SAMPLE_REVIEW], terminal_token),
    ):
        request = CollectionRequest(config=SourceConfig(target_identifier="in.swiggy.android"))
        items = list(connector.collect(request))

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "abc-123"
    assert item.record_type == "app_review"
    assert item.body == "Great app, fast delivery!"
    assert item.rating == 5.0
    assert item.rating_scale_max == 5.0
    assert item.engagement_count == 3
    assert item.author_external_id_hash is not None
    assert item.author_external_id_hash != "Jane Doe"  # PII-010 — never store raw username
    assert item.published_at is not None and item.published_at.tzinfo is not None

    checkpoint = connector.checkpoint()
    assert checkpoint is not None
    assert checkpoint.is_terminal is True


def test_collect_resuming_terminal_checkpoint_returns_immediately() -> None:
    """CHK-009 — resuming a completed run does not launch new work."""
    connector = GooglePlayConnector()
    terminal_checkpoint = ConnectorCheckpoint(
        checkpoint_type="continuation_token", checkpoint_value={}, is_terminal=True
    )

    with patch("instamart_engine.sources.google_play.gp_reviews") as mock_reviews:
        request = CollectionRequest(
            config=SourceConfig(target_identifier="in.swiggy.android"),
            checkpoint=terminal_checkpoint,
        )
        items = list(connector.collect(request))

    mock_reviews.assert_not_called()
    assert items == []


def test_collect_wraps_not_found_as_source_unavailable() -> None:
    from google_play_scraper.exceptions import NotFoundError

    connector = GooglePlayConnector()
    with patch(
        "instamart_engine.sources.google_play.gp_reviews", side_effect=NotFoundError()
    ):
        request = CollectionRequest(config=SourceConfig(target_identifier="in.does.not.exist"))
        with pytest.raises(SourceUnavailableError):
            list(connector.collect(request))
