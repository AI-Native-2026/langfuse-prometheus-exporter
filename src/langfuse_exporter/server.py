"""Minimal HTTP server exposing /metrics, /healthz and a landing page."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

__all__ = ["serve"]

_LANDING = b"""langfuse-prometheus-exporter

Endpoints:
  /metrics   Prometheus metrics
  /healthz   health check
"""


def serve(bind: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        server_version = "langfuse-prometheus-exporter"

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/metrics":
                self._send(200, generate_latest(REGISTRY), CONTENT_TYPE_LATEST)
            elif path in ("/healthz", "/-/healthy", "/-/ready"):
                self._send(200, b"ok\n", "text/plain; charset=utf-8")
            elif path == "/":
                self._send(200, _LANDING, "text/plain; charset=utf-8")
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8")

        def do_HEAD(self):  # noqa: N802
            self.do_GET()

        def log_message(self, *args):  # silence default access logs
            return

    httpd = ThreadingHTTPServer((bind, port), Handler)
    httpd.serve_forever()
