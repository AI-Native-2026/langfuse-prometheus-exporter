import textwrap

import pytest

from langfuse_exporter.loader import load_yaml_definitions

pytest.importorskip("yaml")


def test_load_yaml_definitions(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            metrics:
              - name: langfuse_observations_by_name
                help: Observations by name
                view: observations
                measure: count
                aggregation: count
                group_field: name
                group_label: name
                window: 1h
              - name: langfuse_output_cost
                help: Output cost
                view: observations
                measure: outputCost
                aggregation: sum
                windows: ["1h", "24h"]
            """
        )
    )
    defs = load_yaml_definitions(str(cfg), 50)
    assert len(defs) == 2
    grouped = next(d for d in defs if d.group_field == "name")
    assert grouped.group_label == "name"
    assert grouped.values[0].field == "count_count"
    windowed = next(d for d in defs if d.windows)
    assert [w[0] for w in windowed.windows] == ["1h", "24h"]
    assert windowed.values[0].field == "sum_outputCost"


def test_load_yaml_rejects_both_window_and_group(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            metrics:
              - name: bad
                view: observations
                measure: count
                aggregation: count
                group_field: name
                group_label: name
                windows: ["1h"]
            """
        )
    )
    assert load_yaml_definitions(str(cfg), 50) == []  # invalid item skipped
