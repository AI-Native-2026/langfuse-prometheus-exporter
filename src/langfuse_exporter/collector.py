"""Prometheus custom collector that scrapes the Langfuse Metrics API v2."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.metrics import Counter, Gauge

from .client import MetricsAPIClient, MetricsAPIError
from .queries import MetricDef, MetricValue

__all__ = ["LangfuseCollector", "SelfMetrics"]


class SelfMetrics:
    """Exporter self-instrumentation (registered in the default registry)."""

    def __init__(self, prefix: str = "langfuse_exporter") -> None:
        self.up = Gauge(f"{prefix}_up", "1 if the last scrape of the Metrics API succeeded")
        self.last_success = Gauge(
            f"{prefix}_last_success_timestamp_seconds", "Unix time of the last successful Metrics API scrape"
        )
        self.scrape_duration = Gauge(
            f"{prefix}_scrape_duration_seconds", "Duration of the last full scrape"
        )
        self.api_requests = Counter(
            f"{prefix}_api_requests_total", "Metrics API requests", ["endpoint"]
        )
        self.api_errors = Counter(
            f"{prefix}_api_errors_total", "Metrics API errors", ["endpoint", "kind"]
        )
        self.cache_hits = Counter(
            f"{prefix}_cache_hits_total", "Metrics API responses served from cache", ["endpoint"]
        )


def _fmt_ts(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LangfuseCollector:
    def __init__(
        self,
        client: MetricsAPIClient,
        definitions: List[MetricDef],
        cache_ttl: float = 15.0,
        self_metrics: Optional[SelfMetrics] = None,
        logger: Optional[logging.Logger] = None,
        prefix: str = "langfuse",
    ) -> None:
        self.client = client
        self.definitions = definitions
        self.cache_ttl = cache_ttl
        self.self_metrics = self_metrics or SelfMetrics()
        self.logger = logger or logging.getLogger("langfuse_exporter")
        self.prefix = prefix
        self._cache: Dict[str, tuple] = {}  # key -> (expiry, data_rows)

    # ---- caching ----
    def _query_cached(self, defn: MetricDef, window_seconds: int) -> List[dict]:
        key = f"{id(defn)}:{window_seconds}"
        now = time.time()
        hit = self._cache.get(key)
        if hit and hit[0] > now:
            self.self_metrics.cache_hits.labels("metrics").inc()
            return hit[1]
        to_ts = _fmt_ts(now)
        from_ts = _fmt_ts(now - window_seconds)
        query = defn.build(from_ts, to_ts)
        self.self_metrics.api_requests.labels("metrics").inc()
        data = self.client.query(query).get("data", [])
        self._cache[key] = (now + self.cache_ttl, data)
        return data

    # ---- emission ----
    @staticmethod
    def _emit(defn: MetricDef, row: dict, window_label: Optional[str]):
        """Yield (metric_name, help, labels_dict, value) for one response row."""
        for v in defn.values:
            labels: Dict[str, str] = dict(v.labels)
            if window_label is not None:
                labels["window"] = window_label
            if defn.group_field and defn.group_label:
                labels[defn.group_label] = str(row.get(defn.group_field) or "unknown")
            raw = row.get(v.field)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                # e.g. histogram returns list of tuples; skip non-numeric
                continue
            yield (v.name, v.help, labels, value)

    def collect(self):
        started = time.time()
        families: Dict[str, GaugeMetricFamily] = {}
        label_keys: Dict[str, list] = {}
        ok = True

        def add(name: str, help_text: str, labels: Dict[str, str], value: float):
            keys = sorted(labels.keys())
            fam = families.get(name)
            if fam is None:
                fam = GaugeMetricFamily(name, help_text, labels=keys)
                families[name] = fam
                label_keys[name] = keys
            elif label_keys[name] != keys:
                self.logger.warning("inconsistent labels for %s: %s vs %s", name, label_keys[name], keys)
                return
            fam.add_metric([str(labels[k]) for k in keys], value)

        for defn in self.definitions:
            try:
                if defn.windows:
                    for wname, wsecs in defn.windows:
                        rows = self._query_cached(defn, wsecs)
                        if rows:
                            for item in self._emit(defn, rows[0], wname):
                                add(*item)
                else:
                    rows = self._query_cached(defn, defn.window)
                    for row in rows:
                        for item in self._emit(defn, row, None):
                            add(*item)
            except MetricsAPIError as e:
                ok = False
                kind = type(e).__name__
                self.self_metrics.api_errors.labels("metrics", kind).inc()
                self.logger.warning("metrics query failed (%s): %s", defn.view, e)
            except Exception as e:  # never break a scrape
                ok = False
                self.self_metrics.api_errors.labels("metrics", "unexpected").inc()
                self.logger.exception("unexpected error for %s: %s", defn.view, e)

        self.self_metrics.up.set(1 if ok else 0)
        if ok:
            self.self_metrics.last_success.set(time.time())
        self.self_metrics.scrape_duration.set(time.time() - started)
        yield from families.values()
