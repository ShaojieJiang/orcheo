"""HTTP server for the browser context bridge.

Serves context relay endpoints on localhost for Canvas → CLI communication.
"""

from __future__ import annotations
import json
import logging
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar
from orcheo_sdk.cli.browser_context.store import BrowserContextStore


logger = logging.getLogger(__name__)

_REQUIRED_POST_FIELDS = {"session_id", "page", "focused"}


def _cors_headers() -> dict[str, str]:
    """Return CORS headers allowing any origin (localhost-bound server)."""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _parse_context_body(raw: bytes) -> dict[str, Any] | str:
    """Parse and validate a POST /context body.

    Returns the parsed dict on success, or an error string on failure.
    """
    try:
        body: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "invalid JSON"

    missing = _REQUIRED_POST_FIELDS - set(body.keys())
    if missing:
        return f"missing fields: {', '.join(sorted(missing))}"

    return body


def _resolve_timestamp(body: dict[str, Any]) -> datetime:
    """Extract and parse the timestamp field, falling back to now."""
    if "timestamp" in body:
        try:
            return datetime.fromisoformat(body["timestamp"])
        except (ValueError, TypeError):
            pass
    return datetime.now(UTC)


class ContextRequestHandler(BaseHTTPRequestHandler):
    """Handles context relay HTTP requests.

    Set the ``store`` class variable before use.
    """

    store: ClassVar[BrowserContextStore]

    def _send_json(self, status: int, data: Any) -> None:
        """Send a JSON response with CORS headers."""
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        for key, value in _cors_headers().items():
            self.send_header(key, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_no_content(self) -> None:
        """Send a 204 No Content response with CORS headers."""
        self.send_response(204)
        for key, value in _cors_headers().items():
            self.send_header(key, value)
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS preflight requests."""
        self._send_no_content()

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests for context endpoints."""
        if self.path == "/context":
            self._send_json(200, self.store.get_active())
        elif self.path == "/context/sessions":
            self._send_json(200, self.store.get_all_sessions())
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST /context to upsert a session entry."""
        if self.path != "/context":
            self._send_json(404, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json(400, {"error": "empty body"})
            return

        result = _parse_context_body(self.rfile.read(content_length))
        if isinstance(result, str):
            self._send_json(400, {"error": result})
            return

        self.store.upsert(
            session_id=result["session_id"],
            page=result["page"],
            workflow_id=result.get("workflow_id"),
            workflow_name=result.get("workflow_name"),
            focused=bool(result["focused"]),
            timestamp=_resolve_timestamp(result),
        )
        self._send_no_content()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Route HTTP server log messages to the logger."""
        logger.debug(format, *args)


def create_request_handler(
    store: BrowserContextStore,
) -> type[ContextRequestHandler]:
    """Create a request handler subclass bound to the given store."""
    return type(
        "BoundContextHandler",
        (ContextRequestHandler,),
        {"store": store},
    )


def run_server(*, host: str = "localhost", port: int = 3333) -> None:
    """Start the browser context HTTP server (blocking)."""
    store = BrowserContextStore()
    handler_class = create_request_handler(store)
    server = HTTPServer((host, port), handler_class)
    logger.info("Browser context server listening on %s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
