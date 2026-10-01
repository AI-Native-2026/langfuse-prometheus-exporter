"""Langfuse Metrics API v2 client (stdlib only).

Endpoint: GET /api/public/v2/metrics?query=<url-encoded JSON>
Auth: HTTP Basic (public key : secret key)

Reference: https://langfuse.com/docs/metrics/features/metrics-api
"""
from __future__ import annotations

import base64
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = ["MetricsAPIError", "AuthError", "BadRequestError", "Query", "MetricsAPIClient"]


class MetricsAPIError(Exception):
    """Base error for Metrics API failures."""


class AuthError(MetricsAPIError):
    """401/403 from the Metrics API (check keys)."""


class BadRequestError(MetricsAPIError):
    """400 from the Metrics API (invalid query)."""


@dataclass
class Query:
    """A Metrics API v2 query object."""

    view: str
    metrics: List[Dict[str, str]]
    from_timestamp: str
    to_timestamp: str
    dimensions: List[Dict[str, str]] = field(default_factory=list)
    filters: List[Dict[str, Any]] = field(default_factory=list)
    time_dimension: Optional[Dict[str, str]] = None
    order_by: Optional[List[Dict[str, str]]] = None
    config: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "view": self.view,
            "metrics": self.metrics,
            "dimensions": self.dimensions,
            "filters": self.filters,
            "fromTimestamp": self.from_timestamp,
            "toTimestamp": self.to_timestamp,
        }
        if self.time_dimension is not None:
            d["timeDimension"] = self.time_dimension
        if self.order_by is not None:
            d["orderBy"] = self.order_by
        if self.config is not None:
            d["config"] = self.config
        return d


class MetricsAPIClient:
    def __init__(
        self,
        host: str,
        public_key: str,
        secret_key: str,
        timeout: float = 20.0,
        verify_ssl: bool = True,
        user_agent: str = "langfuse-prometheus-exporter",
    ) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.user_agent = user_agent
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self._auth_header = f"Basic {token}"

    def query(self, q: Query) -> Dict[str, Any]:
        """Run a query and return the parsed JSON response ({'data': [...]})."""
        payload = urllib.parse.urlencode({"query": json.dumps(q.to_dict())})
        url = f"{self.host}/api/public/v2/metrics?{payload}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": self._auth_header,
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            if e.code in (401, 403):
                raise AuthError(f"HTTP {e.code} from Metrics API: {body}") from e
            if e.code == 400:
                raise BadRequestError(f"HTTP 400 from Metrics API: {body}") from e
            raise MetricsAPIError(f"HTTP {e.code} from Metrics API: {body}") from e
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise MetricsAPIError(f"request failed: {e}") from e
        except json.JSONDecodeError as e:
            raise MetricsAPIError(f"invalid JSON response: {e}") from e
