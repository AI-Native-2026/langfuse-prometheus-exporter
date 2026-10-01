from langfuse_exporter.collector import LangfuseCollector
from langfuse_exporter.queries import default_definitions


class FakeMetric:
    def labels(self, *a, **k):
        return self

    def inc(self, *a, **k):
        return None

    def set(self, *a, **k):
        return None


class FakeSelfMetrics:
    def __init__(self):
        self.up = FakeMetric()
        self.last_success = FakeMetric()
        self.scrape_duration = FakeMetric()
        self.api_requests = FakeMetric()
        self.api_errors = FakeMetric()
        self.cache_hits = FakeMetric()


class FakeClient:
    def __init__(self):
        self.calls = 0

    def query(self, q):
        self.calls += 1
        m = q.metrics[0]
        key = f"{m['aggregation']}_{m['measure']}"
        if q.dimensions:
            field = q.dimensions[0]["field"]
            return {"data": [{key: 10.0, field: "SPAN"}, {key: 5.0, field: "GENERATION"}]}
        return {"data": [{key: 3.0}]}


def test_collector_emits_expected_families():
    defs = default_definitions(["1h"], 50)
    collector = LangfuseCollector(
        FakeClient(), defs, cache_ttl=0, self_metrics=FakeSelfMetrics()
    )
    families = {f.name: f for f in collector.collect()}
    assert "langfuse_observations_count" in families
    assert "langfuse_cost_usd" in families
    assert "langfuse_observation_latency_ms" in families
    assert "langfuse_observations_by_type" in families
    assert "langfuse_scores_count" in families

    # windowed count has a single sample with window label
    fam = families["langfuse_observations_count"]
    assert fam.samples[0].labels == {"window": "1h"}
    assert fam.samples[0].value == 3.0

    # grouped by type emitted per dimension value
    tvals = {s.labels["type"] for s in families["langfuse_observations_by_type"].samples}
    assert tvals == {"SPAN", "GENERATION"}


def test_collector_caches_within_ttl():
    client = FakeClient()
    defs = default_definitions(["1h"], 50)
    collector = LangfuseCollector(client, defs, cache_ttl=3600, self_metrics=FakeSelfMetrics())
    list(collector.collect())
    first = client.calls
    list(collector.collect())
    assert client.calls == first  # served from cache
