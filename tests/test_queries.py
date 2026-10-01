from langfuse_exporter.queries import default_definitions, parse_window, vf


def test_parse_window():
    assert parse_window("30s") == 30
    assert parse_window("5m") == 300
    assert parse_window("1h") == 3600
    assert parse_window("24h") == 86400
    assert parse_window("7d") == 604800
    assert parse_window("45") == 45


def test_value_field():
    assert vf("count", "count") == "count_count"
    assert vf("totalCost", "sum") == "sum_totalCost"
    assert vf("latency", "p95") == "p95_latency"


def test_default_definitions_present():
    defs = default_definitions(["5m", "1h", "24h"], 50)
    names = {v.name for d in defs for v in d.values}
    for expected in (
        "langfuse_observations_count",
        "langfuse_observation_latency_ms",
        "langfuse_tokens",
        "langfuse_cost_usd",
        "langfuse_observations_by_type",
        "langfuse_observations_by_model",
        "langfuse_cost_usd_by_model",
        "langfuse_scores_count",
        "langfuse_scores_avg",
        "langfuse_scores_boolean_rate",
    ):
        assert expected in names


def test_build_query_windowed_and_grouped():
    defs = default_definitions(["1h"], 50)
    windowed = next(d for d in defs if d.windows)
    q = windowed.build("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
    d = q.to_dict()
    assert d["view"] == "observations"
    assert d["dimensions"] == []
    assert d["config"]["row_limit"] == 50

    grouped = next(d for d in defs if d.group_field == "type")
    gq = grouped.build("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
    gd = gq.to_dict()
    assert gd["dimensions"] == [{"field": "type"}]
    assert gd["orderBy"][0]["direction"] == "desc"
