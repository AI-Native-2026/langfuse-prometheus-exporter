"""Metric definitions: map Langfuse Metrics API v2 queries to Prometheus series."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .client import Query

__all__ = ["MetricValue", "MetricDef", "default_definitions", "parse_window"]


def parse_window(text: str) -> int:
    """'30s' | '5m' | '1h' | '24h' | '7d' -> seconds."""
    text = text.strip().lower()
    if not text:
        raise ValueError("empty window")
    unit = text[-1]
    num = text[:-1]
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(unit)
    if mult is None:
        # bare number -> seconds
        return int(float(text))
    return int(float(num) * mult)


def vf(measure: str, aggregation: str) -> str:
    """Response field name for a metric: {aggregation}_{measure}."""
    return f"{aggregation}_{measure}"


@dataclass
class MetricValue:
    """One Prometheus metric family emitted from a query response row."""

    name: str
    help: str
    field: str  # response key, e.g. "sum_totalCost"
    labels: Dict[str, str] = field(default_factory=dict)  # constant labels


@dataclass
class MetricDef:
    """A Metrics API query plus how to turn its rows into Prometheus metrics.

    If ``windows`` is set, the query is run once per window (aggregated, single
    row) and each emitted series carries a ``window`` label.
    Otherwise the query is run once over ``window`` seconds and, if
    ``group_field`` is set, emits one series per dimension value.
    """

    view: str
    metrics: List[Dict[str, str]]
    values: List[MetricValue]
    group_field: Optional[str] = None
    group_label: Optional[str] = None
    windows: Optional[List[Tuple[str, int]]] = None
    window: int = 3600
    row_limit: int = 50
    filters: List[Dict[str, Any]] = field(default_factory=list)
    granularity: Optional[str] = None
    order_desc: Optional[str] = None  # order grouped results by this response field desc

    def build(self, from_ts: str, to_ts: str) -> Query:
        dims = [{"field": self.group_field}] if self.group_field else []
        order_by = [{"field": self.order_desc, "direction": "desc"}] if (self.group_field and self.order_desc) else None
        return Query(
            view=self.view,
            metrics=self.metrics,
            dimensions=dims,
            filters=self.filters,
            from_timestamp=from_ts,
            to_timestamp=to_ts,
            time_dimension={"granularity": self.granularity} if self.granularity else None,
            order_by=order_by,
            config={"row_limit": self.row_limit},
        )


def default_definitions(windows: List[str], row_limit: int) -> List[MetricDef]:
    w = [(name, parse_window(name)) for name in windows]
    count = [{"measure": "count", "aggregation": "count"}]
    defs: List[MetricDef] = []

    # --- windowed aggregates (single row per window) ---
    defs.append(MetricDef(
        view="observations", metrics=count, windows=w,
        values=[MetricValue("langfuse_observations_count", "Observations in window", vf("count", "count"))],
    ))
    defs.append(MetricDef(
        view="observations",
        metrics=[{"measure": "latency", "aggregation": a} for a in ("avg", "p50", "p90", "p95", "p99")],
        windows=w,
        values=[
            MetricValue("langfuse_observation_latency_ms", "Observation latency (ms)", vf("latency", "avg"), {"quantile": "avg"}),
            MetricValue("langfuse_observation_latency_ms", "Observation latency (ms)", vf("latency", "p50"), {"quantile": "p50"}),
            MetricValue("langfuse_observation_latency_ms", "Observation latency (ms)", vf("latency", "p90"), {"quantile": "p90"}),
            MetricValue("langfuse_observation_latency_ms", "Observation latency (ms)", vf("latency", "p95"), {"quantile": "p95"}),
            MetricValue("langfuse_observation_latency_ms", "Observation latency (ms)", vf("latency", "p99"), {"quantile": "p99"}),
        ],
    ))
    defs.append(MetricDef(
        view="observations",
        metrics=[{"measure": m, "aggregation": "sum"} for m in ("inputTokens", "outputTokens", "totalTokens")],
        windows=w,
        values=[
            MetricValue("langfuse_tokens", "Tokens consumed in window", vf("inputTokens", "sum"), {"type": "input"}),
            MetricValue("langfuse_tokens", "Tokens consumed in window", vf("outputTokens", "sum"), {"type": "output"}),
            MetricValue("langfuse_tokens", "Tokens consumed in window", vf("totalTokens", "sum"), {"type": "total"}),
        ],
    ))
    defs.append(MetricDef(
        view="observations",
        metrics=[{"measure": m, "aggregation": "sum"} for m in ("inputCost", "outputCost", "totalCost")],
        windows=w,
        values=[
            MetricValue("langfuse_cost_usd", "Cost (USD) in window", vf("inputCost", "sum"), {"type": "input"}),
            MetricValue("langfuse_cost_usd", "Cost (USD) in window", vf("outputCost", "sum"), {"type": "output"}),
            MetricValue("langfuse_cost_usd", "Cost (USD) in window", vf("totalCost", "sum"), {"type": "total"}),
        ],
    ))

    # --- grouped (single window) ---
    defs.append(MetricDef(
        view="observations", metrics=count, window=3600, row_limit=row_limit,
        group_field="type", group_label="type", order_desc=vf("count", "count"),
        values=[MetricValue("langfuse_observations_by_type", "Observations by type (1h)", vf("count", "count"))],
    ))
    defs.append(MetricDef(
        view="observations", metrics=count, window=3600, row_limit=row_limit,
        group_field="providedModelName", group_label="model", order_desc=vf("count", "count"),
        values=[MetricValue("langfuse_observations_by_model", "Observations by model (1h)", vf("count", "count"))],
    ))
    defs.append(MetricDef(
        view="observations", metrics=count, window=3600, row_limit=row_limit,
        group_field="name", group_label="name", order_desc=vf("count", "count"),
        values=[MetricValue("langfuse_observations_by_name", "Observations by name (1h)", vf("count", "count"))],
    ))
    defs.append(MetricDef(
        view="observations", metrics=count, window=3600, row_limit=row_limit,
        group_field="environment", group_label="environment", order_desc=vf("count", "count"),
        values=[MetricValue("langfuse_observations_by_environment", "Observations by environment (1h)", vf("count", "count"))],
    ))
    defs.append(MetricDef(
        view="observations", metrics=[{"measure": "totalCost", "aggregation": "sum"}],
        window=86400, row_limit=row_limit,
        group_field="providedModelName", group_label="model", order_desc=vf("totalCost", "sum"),
        values=[MetricValue("langfuse_cost_usd_by_model", "Cost (USD) by model (24h)", vf("totalCost", "sum"))],
    ))

    # --- scores ---
    for view, stype in (("scores-numeric", "numeric"), ("scores-boolean", "boolean"), ("scores-categorical", "categorical")):
        defs.append(MetricDef(
            view=view, metrics=count, window=86400,
            values=[MetricValue("langfuse_scores_count", "Scores in window by data type", vf("count", "count"), {"type": stype})],
        ))
    defs.append(MetricDef(
        view="scores-numeric", metrics=[{"measure": "value", "aggregation": "avg"}],
        window=86400, row_limit=row_limit, group_field="name", group_label="name",
        order_desc=None,
        values=[MetricValue("langfuse_scores_avg", "Average numeric score by name (24h)", vf("value", "avg"))],
    ))
    defs.append(MetricDef(
        view="scores-boolean", metrics=[{"measure": "value", "aggregation": "avg"}],
        window=86400, row_limit=row_limit, group_field="name", group_label="name",
        values=[MetricValue("langfuse_scores_boolean_rate", "Boolean score true-rate by name (24h)", vf("value", "avg"))],
    ))
    return defs
