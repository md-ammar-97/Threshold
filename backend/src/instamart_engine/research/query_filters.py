"""Deterministic query-plan filter validation. edgecases.md QRY-010/011/018;
architecture.md §17.2 "planner output is validated before execution".

The planner LLM may return any filter keys/values it likes in
`structured_filters`; this module is the backstop that turns that into
`effective_filters` — the only filters retrieval is ever allowed to apply.
"""

from datetime import date

from instamart_engine.analysis.demographic_guard import contains_demographic_inference

ALLOWED_FILTER_KEYS = frozenset(
    {
        "source_connector_key",
        "date_from",
        "date_to",
        "taxonomy_dimension_key",
        "taxonomy_label_key",
    }
)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def validate_filters(raw_filters: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Returns (effective_filters, warnings). Never raises — an invalid
    filter is dropped and warned about, not a hard failure (QRY-010)."""
    effective: dict[str, str] = {}
    warnings: list[str] = []

    for key, value in raw_filters.items():
        if key not in ALLOWED_FILTER_KEYS:
            # QRY-010 — reject an unknown/invalid filter key rather than
            # passing it through to a query builder that doesn't expect it.
            warnings.append(f"Ignored unsupported filter key: {key!r}")
            continue

        if not isinstance(value, str) or not value.strip():
            warnings.append(f"Ignored empty filter value for {key!r}")
            continue

        if contains_demographic_inference(value):
            # QRY-011 — the planner attempted to filter on an unsupported
            # inferred demographic attribute; strip it and warn rather than
            # silently applying it.
            warnings.append(f"Removed unsupported demographic filter: {key!r}")
            continue

        if key in ("date_from", "date_to") and _parse_date(value) is None:
            warnings.append(f"Ignored unparseable date filter {key!r}={value!r}")
            continue

        effective[key] = value

    if (
        "date_from" in effective
        and "date_to" in effective
        and _parse_date(effective["date_from"]) > _parse_date(effective["date_to"])  # type: ignore[operator]
    ):
        warnings.append("date_from was after date_to; both date filters were ignored")
        del effective["date_from"]
        del effective["date_to"]

    return effective, warnings
