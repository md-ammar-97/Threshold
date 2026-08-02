from instamart_engine.research.query_filters import validate_filters


def test_unknown_filter_key_is_dropped() -> None:
    effective, warnings = validate_filters({"unknown_key": "value"})
    assert effective == {}
    assert any("unknown_key" in w for w in warnings)


def test_demographic_filter_value_is_dropped() -> None:
    effective, warnings = validate_filters({"taxonomy_label_key": "young professional"})
    assert effective == {}
    assert any("demographic" in w.lower() for w in warnings)


def test_unparseable_date_is_dropped() -> None:
    effective, warnings = validate_filters({"date_from": "not-a-date"})
    assert effective == {}
    assert any("unparseable" in w.lower() for w in warnings)


def test_date_from_after_date_to_drops_both() -> None:
    effective, warnings = validate_filters({"date_from": "2026-06-01", "date_to": "2026-01-01"})
    assert effective == {}
    assert any("date_from was after date_to" in w for w in warnings)


def test_valid_filters_pass_through() -> None:
    effective, warnings = validate_filters(
        {
            "source_connector_key": "google_play",
            "date_from": "2026-01-01",
            "date_to": "2026-06-01",
            "taxonomy_dimension_key": "exploration_barrier",
        }
    )
    assert effective == {
        "source_connector_key": "google_play",
        "date_from": "2026-01-01",
        "date_to": "2026-06-01",
        "taxonomy_dimension_key": "exploration_barrier",
    }
    assert warnings == []


def test_empty_value_is_dropped() -> None:
    effective, warnings = validate_filters({"source_connector_key": "   "})
    assert effective == {}
    assert any("empty" in w.lower() for w in warnings)
