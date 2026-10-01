"""Entry point: wire config, client, definitions, collector and HTTP server."""
from __future__ import annotations

import logging
import signal
import sys

from prometheus_client import REGISTRY

from .client import MetricsAPIClient
from .collector import LangfuseCollector, SelfMetrics
from .config import load_config
from .loader import load_yaml_definitions
from .queries import default_definitions
from .server import serve
from .version import __version__

__all__ = ["main"]


def main(argv=None) -> int:
    cfg = load_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("langfuse_exporter")
    try:
        cfg.validate()
    except ValueError as e:
        log.error("invalid configuration: %s", e)
        return 2

    log.info("starting langfuse-prometheus-exporter %s -> %s", __version__, cfg.host)

    defs = default_definitions(cfg.windows, cfg.row_limit) if cfg.default_metrics else []
    if cfg.config_file:
        defs += load_yaml_definitions(cfg.config_file, cfg.row_limit)
    if not defs:
        log.error("no metric definitions loaded (enable default metrics or set EXPORTER_CONFIG)")
        return 2

    client = MetricsAPIClient(
        host=cfg.host,
        public_key=cfg.public_key,
        secret_key=cfg.secret_key,
        timeout=cfg.timeout_seconds,
        verify_ssl=cfg.verify_ssl,
        user_agent=f"langfuse-prometheus-exporter/{__version__}",
    )
    collector = LangfuseCollector(
        client=client,
        definitions=defs,
        cache_ttl=cfg.cache_ttl_seconds,
        self_metrics=SelfMetrics(),
    )
    REGISTRY.register(collector)

    def _shutdown(signum, frame):  # noqa: ARG001
        log.info("received signal %s, exiting", signum)
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, AttributeError):  # pragma: no cover
            pass

    log.info("listening on %s:%d/metrics", cfg.bind, cfg.port)
    serve(cfg.bind, cfg.port)
    return 0
