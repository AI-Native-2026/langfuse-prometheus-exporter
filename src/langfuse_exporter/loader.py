"""Load custom metric definitions from a YAML file (optional)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .queries import MetricDef, MetricValue, parse_window, vf

__all__ = ["load_yaml_definitions"]

_LOG = logging.getLogger("langfuse_exporter")


def load_yaml_definitions(path: str, default_row_limit: int = 50) -> List[MetricDef]:
    """Parse a YAML file with a top-level ``metrics:`` list into MetricDef.

    Example::

        metrics:
          - name: langfuse_observations_by_name
            help: Observations by name
            view: observations
            measure: count
            aggregation: count
            group_field: name
            group_label: name
            window: 1h
    """
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover
        _LOG.warning("EXPORTER_CONFIG is set but PyYAML is not installed; ignoring custom metrics")
        return []

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    items = raw.get("metrics") or []
    defs: List[MetricDef] = []
    for i, it in enumerate(items):
        try:
            defs.append(_parse_item(it, default_row_limit))
        except Exception as e:
            _LOG.warning("invalid custom metric #%d: %s", i, e)
    _LOG.info("loaded %d custom metric definition(s) from %s", len(defs), path)
    return defs


def _parse_item(it: Dict[str, Any], default_row_limit: int) -> MetricDef:
    view = it["view"]
    measure = it["measure"]
    aggregation = it["aggregation"]
    name = it["name"]
    help_text = it.get("help", name)
    labels = dict(it.get("labels") or {})
    group_field = it.get("group_field")
    group_label = it.get("group_label")
    if group_field and not group_label:
        raise ValueError("group_label is required when group_field is set")
    windows = it.get("windows")
    window = it.get("window")
    if windows and group_field:
        raise ValueError("windows and group_field are mutually exclusive")
    win_list = [(str(w), parse_window(str(w))) for w in windows] if windows else None
    window_secs = parse_window(str(window)) if window else 3600
    value = MetricValue(name, help_text, it.get("value_field") or vf(measure, aggregation), labels)
    return MetricDef(
        view=view,
        metrics=[{"measure": measure, "aggregation": aggregation}],
        values=[value],
        group_field=group_field,
        group_label=group_label,
        windows=win_list,
        window=window_secs,
        row_limit=int(it.get("row_limit", default_row_limit)),
        filters=it.get("filters") or [],
        granularity=it.get("granularity"),
        order_desc=it.get("order_desc"),
    )
