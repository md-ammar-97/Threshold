"""Shared base for Apify-actor-backed connectors. architecture.md §10.2/§34.4.

Wraps Apify's `run-sync-get-dataset-items` REST endpoint: runs an actor
synchronously (bounded by `timeout_seconds`) and returns its output dataset
items directly, without polling a separate run-status endpoint. Platform
connectors (Reddit, Twitter/X, Instagram, Facebook, Apple App Store)
subclass this and only implement `actor_id`, `_build_actor_input`, and
`_to_raw_item`.

Each `collect()` call is treated as one terminal run (Apify's sync endpoint
has no equivalent of Google Play's native continuation token) — re-running
the same collection config later re-collects fresh results, and the
existing `UNIQUE(source_connector_id, external_id)` constraint on
`raw_source_item` (datamodel.md §10) naturally dedupes across runs.

Every subclass is genuinely pay-per-result (unlike google_play/public_web);
SRC-018 cost-cap enforcement is not implemented anywhere in this codebase
yet (a pre-existing gap, not introduced here) — monitor Apify usage
manually until that lands.
"""

from collections.abc import Iterator
from typing import Any

import httpx

from instamart_engine.sources.base import (
    CollectionRequest,
    ConnectorCheckpoint,
    RawSourceItem,
    SourceConfig,
)
from instamart_engine.sources.exceptions import (
    SourceAuthError,
    SourceRateLimitedError,
    SourceTransientError,
    SourceUnavailableError,
)

APIFY_BASE_URL = "https://api.apify.com/v2"


class ApifyActorConnector:
    """Subclasses must set `actor_id`/`source_name` and implement
    `_build_actor_input`/`_to_raw_item`."""

    actor_id: str
    source_name: str

    def __init__(
        self,
        *,
        api_token: str,
        timeout_seconds: float = 240.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_token:
            raise SourceAuthError(f"{self.source_name}: APIFY_TOKEN is not configured")
        self._token = api_token
        self._client = client or httpx.Client(
            base_url=APIFY_BASE_URL, timeout=timeout_seconds + 10.0
        )
        self._last_checkpoint: ConnectorCheckpoint | None = None

    def _actor_path(self) -> str:
        return self.actor_id.replace("/", "~")

    def _build_actor_input(self, config: SourceConfig) -> dict[str, Any]:
        raise NotImplementedError

    def _to_raw_item(self, item: dict[str, Any]) -> RawSourceItem | None:
        """Return `None` to skip a dataset item that isn't a usable record
        (e.g. an actor status/error row rather than actual content)."""
        raise NotImplementedError

    def validate_config(self, config: SourceConfig) -> None:
        """Subclasses override for source-specific requirements (e.g. a
        non-empty URL list, non-empty search terms)."""

    def collect(self, request: CollectionRequest) -> Iterator[RawSourceItem]:
        # Unlike paginated connectors (Google Play, Apple App Store), an
        # Apify actor call is always a single terminal run with no
        # continuation token — `is_terminal` on a prior checkpoint just
        # records that that earlier run finished, not that this config can
        # never collect again. Skipping collection here previously blocked
        # every run after the first for a given collection config.
        config = request.config
        self.validate_config(config)

        actor_input = self._build_actor_input(config)

        try:
            response = self._client.post(
                f"/acts/{self._actor_path()}/run-sync-get-dataset-items",
                params={"token": self._token},
                json=actor_input,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                raise SourceAuthError(
                    f"{self.source_name}: Apify auth failed ({status})"
                ) from exc
            if status == 429:
                retry_after = exc.response.headers.get("retry-after")
                raise SourceRateLimitedError(
                    f"{self.source_name}: Apify rate limited",
                    retry_after_seconds=float(retry_after) if retry_after else None,
                ) from exc
            if 500 <= status < 600:
                raise SourceTransientError(
                    f"{self.source_name}: Apify server error {status}"
                ) from exc
            raise SourceUnavailableError(
                f"{self.source_name}: Apify request failed ({status}): {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SourceTransientError(
                f"{self.source_name}: network error calling Apify: {exc}"
            ) from exc

        limit = config.record_limit
        yielded = 0
        for raw_item in response.json():
            if limit is not None and yielded >= limit:
                break
            mapped = self._to_raw_item(raw_item)
            if mapped is None:
                continue
            yield mapped
            yielded += 1

        self._last_checkpoint = ConnectorCheckpoint(
            checkpoint_type="apify_run",
            checkpoint_value={"actor_id": self.actor_id},
            is_terminal=True,
        )

    def checkpoint(self) -> ConnectorCheckpoint | None:
        return self._last_checkpoint
