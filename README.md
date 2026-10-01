# langfuse-prometheus-exporter

A Prometheus exporter for **[Langfuse](https://langfuse.com) Metrics API v2** — expose
LLM observability metrics (request volume, latency, cost, tokens, scores) from your
self-hosted (or cloud) Langfuse project as Prometheus metrics, so you can alert and
dashboard them in Grafana.

It is a small, dependency-light service (Python + `prometheus-client`) that on each
scrape queries the official `GET /api/public/v2/metrics` endpoint and maps the
results to Prometheus gauges.

> Requires **Langfuse v4+** (the v2 Metrics API). For self-hosted v3, use the v1 endpoint.

## Metrics exposed

| Metric | Labels | Description |
|---|---|---|
| `langfuse_observations_count` | `window` | Observations per window (5m/1h/24h by default) |
| `langfuse_observation_latency_ms` | `window`, `quantile` | Latency avg/p50/p90/p95/p99 (ms) |
| `langfuse_tokens` | `window`, `type` | Tokens (input/output/total) |
| `langfuse_cost_usd` | `window`, `type` | Cost USD (input/output/total) |
| `langfuse_observations_by_type` | `type` | Observations by type (1h) |
| `langfuse_observations_by_model` | `model` | Observations by model (1h) |
| `langfuse_observations_by_name` | `name` | Observations by name (1h) |
| `langfuse_observations_by_environment` | `environment` | Observations by environment (1h) |
| `langfuse_cost_usd_by_model` | `model` | Cost USD by model (24h) |
| `langfuse_scores_count` | `type` | Number of scores by data type (24h) |
| `langfuse_scores_avg` | `name` | Average numeric score by name (24h) |
| `langfuse_scores_boolean_rate` | `name` | Boolean score true-rate by name (24h) |

Exporter self-metrics:

| Metric | Description |
|---|---|
| `langfuse_exporter_up` | `1` if the last scrape of the Metrics API succeeded |
| `langfuse_exporter_last_success_timestamp_seconds` | Unix time of last successful scrape |
| `langfuse_exporter_scrape_duration_seconds` | Duration of the last scrape |
| `langfuse_exporter_api_requests_total` | Metrics API requests |
| `langfuse_exporter_api_errors_total` | Metrics API errors by kind |
| `langfuse_exporter_cache_hits_total` | Responses served from cache |

## Quick start

### Docker

```bash
# Same docker network as your Langfuse stack (default: langfuse_default)
LANGFUSE_PUBLIC_KEY=pk-lf-... \
LANGFUSE_SECRET_KEY=sk-lf-... \
docker compose up -d
curl http://localhost:9101/metrics
```

### pip

```bash
pip install .
LANGFUSE_HOST=http://localhost:3000 \
LANGFUSE_PUBLIC_KEY=pk-lf-... \
LANGFUSE_SECRET_KEY=sk-lf-... \
langfuse-prometheus-exporter
```

### Prometheus scrape config

```yaml
scrape_configs:
  - job_name: langfuse
    static_configs:
      - targets: ["langfuse-prometheus-exporter:9101"]
```

## Configuration

All via environment variables:

| Variable | Default | Description |
|---|---|---|
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse base URL (self-hosted or cloud) |
| `LANGFUSE_PUBLIC_KEY` | — | **Required.** Project public key (`pk-lf-...`) |
| `LANGFUSE_SECRET_KEY` | — | **Required.** Project secret key (`sk-lf-...`) |
| `EXPORTER_BIND` | `0.0.0.0` | Listen address |
| `EXPORTER_PORT` | `9101` | Listen port |
| `EXPORTER_WINDOWS` | `5m,1h,24h` | Comma-separated windows for windowed metrics |
| `EXPORTER_CACHE_TTL_SECONDS` | `15` | Cache TTL for API responses (reduces API load) |
| `EXPORTER_TIMEOUT_SECONDS` | `20` | HTTP timeout |
| `EXPORTER_ROW_LIMIT` | `50` | Max rows for grouped queries (API max 1000) |
| `EXPORTER_VERIFY_SSL` | `true` | Verify TLS certificates |
| `EXPORTER_LOG_LEVEL` | `info` | `debug`/`info`/`warning`/`error` |
| `EXPORTER_DEFAULT_METRICS` | `true` | Emit the built-in metric set |
| `EXPORTER_CONFIG` | — | Path to a YAML file with extra metric definitions (needs `PyYAML`) |

## Custom metrics (YAML)

Add arbitrary metrics from the Metrics API without changing code:

```yaml
# examples/config.yaml
metrics:
  - name: langfuse_observations_by_name
    help: "Observations by name (1h)"
    view: observations
    measure: count
    aggregation: count
    group_field: name
    group_label: name
    window: 1h
    row_limit: 50

  - name: langfuse_output_cost
    help: "Output cost (USD)"
    view: observations
    measure: outputCost
    aggregation: sum
    windows: ["1h", "24h"]
```

Run with `EXPORTER_CONFIG=/app/examples/config.yaml`.

Supported in a definition: `view`, `measure`, `aggregation`, `group_field`,
`group_label`, `window` **or** `windows`, `labels` (constant labels), `row_limit`,
`filters`, `granularity`, `value_field`, `order_desc`.

## Metrics API v2 reference (condensed)

Endpoint: `GET /api/public/v2/metrics?query=<url-encoded JSON>` (HTTP Basic auth).

**Views:** `observations`, `scores-numeric`, `scores-boolean`, `scores-categorical`
(`traces` is not available in v2).

**Observations measures:** `count`, `latency`, `streamingLatency`, `inputTokens`,
`outputTokens`, `totalTokens`, `outputTokensPerSecond`, `tokensPerSecond`,
`inputCost`, `outputCost`, `totalCost`, `timeToFirstToken`, `countScores`.

**Aggregations:** `sum`, `avg`, `count`, `max`, `min`, `p50`, `p75`, `p90`, `p95`,
`p99`, `histogram`, `uniq`.

**Dimensions (observations):** `environment`, `type`, `name`, `level`, `version`,
`tags`, `release`, `traceName`, `traceRelease`, `traceVersion`, `providedModelName`,
`promptName`, `promptVersion`, `isRootObservation`, `startTimeMonth`.
(High-cardinality fields — `id`, `traceId`, `userId`, `sessionId`,
`parentObservationId` — are filter-only.)

**timeDimension.granularity:** `auto`, `minute`, `hour`, `day`, `week`, `month`.

**Response field naming:** each metric becomes `{aggregation}_{measure}`, e.g.
`count_count`, `sum_totalCost`, `p95_latency`, `avg_value`.

## Development

```bash
pip install -e ".[yaml,test]"
pytest
```

## License

Apache-2.0. See [LICENSE](LICENSE).

Langfuse is a trademark of its respective owners; this project is an independent
integration and is not affiliated with Langfuse.
