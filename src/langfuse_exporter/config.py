"""Exporter configuration (environment variables + optional YAML)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v not in (None, "") else default


def _float(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v not in (None, "") else default


@dataclass
class ExporterConfig:
    host: str = "http://localhost:3000"
    public_key: str = ""
    secret_key: str = ""
    bind: str = "0.0.0.0"
    port: int = 9101
    cache_ttl_seconds: float = 15.0
    timeout_seconds: float = 20.0
    verify_ssl: bool = True
    windows: List[str] = field(default_factory=lambda: ["5m", "1h", "24h"])
    row_limit: int = 50
    log_level: str = "info"
    config_file: Optional[str] = None
    default_metrics: bool = True

    def validate(self) -> None:
        missing = [k for k, v in (("LANGFUSE_PUBLIC_KEY", self.public_key),
                                  ("LANGFUSE_SECRET_KEY", self.secret_key)) if not v]
        if missing:
            raise ValueError(f"missing required environment variable(s): {', '.join(missing)}")
        if not self.windows:
            raise ValueError("EXPORTER_WINDOWS must contain at least one window")


def load_config() -> ExporterConfig:
    windows = [w.strip() for w in os.environ.get("EXPORTER_WINDOWS", "5m,1h,24h").split(",") if w.strip()]
    return ExporterConfig(
        host=os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
        bind=os.environ.get("EXPORTER_BIND", "0.0.0.0"),
        port=_int("EXPORTER_PORT", 9101),
        cache_ttl_seconds=_float("EXPORTER_CACHE_TTL_SECONDS", 15.0),
        timeout_seconds=_float("EXPORTER_TIMEOUT_SECONDS", 20.0),
        verify_ssl=_bool("EXPORTER_VERIFY_SSL", True),
        windows=windows,
        row_limit=_int("EXPORTER_ROW_LIMIT", 50),
        log_level=os.environ.get("EXPORTER_LOG_LEVEL", "info"),
        config_file=os.environ.get("EXPORTER_CONFIG") or None,
        default_metrics=_bool("EXPORTER_DEFAULT_METRICS", True),
    )
