import base64
import json
import urllib.error
from unittest import mock

import pytest

from langfuse_exporter.client import AuthError, BadRequestError, MetricsAPIClient, MetricsAPIError, Query


def _client():
    return MetricsAPIClient("http://langfuse:3000", "pk-test", "sk-test")


def test_auth_header():
    c = _client()
    expected = base64.b64encode(b"pk-test:sk-test").decode()
    assert c._auth_header == f"Basic {expected}"


def test_query_to_dict_omits_optional():
    q = Query(
        view="observations",
        metrics=[{"measure": "count", "aggregation": "count"}],
        from_timestamp="2026-01-01T00:00:00Z",
        to_timestamp="2026-01-01T01:00:00Z",
    )
    d = q.to_dict()
    assert d["view"] == "observations"
    assert d["dimensions"] == []
    assert "timeDimension" not in d
    assert "orderBy" not in d


def test_query_includes_optional():
    q = Query(
        view="observations",
        metrics=[{"measure": "totalCost", "aggregation": "sum"}],
        from_timestamp="a",
        to_timestamp="b",
        dimensions=[{"field": "providedModelName"}],
        time_dimension={"granularity": "hour"},
        order_by=[{"field": "sum_totalCost", "direction": "desc"}],
        config={"row_limit": 10},
    )
    d = q.to_dict()
    assert d["dimensions"] == [{"field": "providedModelName"}]
    assert d["timeDimension"] == {"granularity": "hour"}
    assert d["config"] == {"row_limit": 10}


def test_query_http_error_mapping():
    c = _client()
    q = Query("observations", [{"measure": "count", "aggregation": "count"}], "a", "b")

    err = urllib.error.HTTPError("u", 401, "unauthorized", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(AuthError):
            c.query(q)

    err = urllib.error.HTTPError("u", 400, "bad", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(BadRequestError):
            c.query(q)

    err = urllib.error.HTTPError("u", 500, "boom", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(MetricsAPIError):
            c.query(q)


def test_query_success():
    c = _client()
    q = Query("observations", [{"measure": "count", "aggregation": "count"}], "a", "b")
    body = json.dumps({"data": [{"count_count": 5}]}).encode()

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return body

    with mock.patch("urllib.request.urlopen", return_value=Resp()):
        assert c.query(q)["data"][0]["count_count"] == 5
