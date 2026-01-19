#!/usr/bin/env python3
"""Lightweight placeholder development server for ChessGuard.

This script serves mock data from the ``seeds`` directory so that
contributors can validate their local environment while the real backend
is under construction.
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT_DIR / "seeds"


def _load_seed_file(file_name: str) -> Tuple[HTTPStatus, Dict[str, Any]]:
    """Load a JSON seed file and return a response payload."""

    file_path = SEED_DIR / file_name
    if not file_path.exists():
        return (
            HTTPStatus.NOT_FOUND,
            {
                "error": f"Seed file '{file_name}' is missing.",
                "available_files": [p.name for p in SEED_DIR.glob("*.json")],
            },
        )

    with file_path.open("r", encoding="utf-8") as stream:
        data: List[Dict[str, Any]] = json.load(stream)

    return (
        HTTPStatus.OK,
        {
            "count": len(data),
            "data": data,
        },
    )


class ChessGuardRequestHandler(BaseHTTPRequestHandler):
    """Request handler exposing a handful of mock endpoints."""

    server_version = "ChessGuardPlaceholder/0.1"

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (method name required by BaseHTTPRequestHandler)
        """Respond to GET requests with mock data."""

        if self.path in {"/", "/health"}:
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "environment": os.getenv("APP_ENV", "development"),
                    "log_level": os.getenv("LOG_LEVEL", "INFO"),
                },
            )
            return

        if self.path == "/players":
            status, payload = _load_seed_file("sample_players.json")
            self._send_json(status, payload)
            return

        if self.path == "/games":
            status, payload = _load_seed_file("sample_games.json")
            self._send_json(status, payload)
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "Route not found.",
                "supported_routes": ["/", "/health", "/players", "/games"],
            },
        )

    # Silence the default logging noise so console output stays clean.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - keeping signature for compatibility
        if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            super().log_message(format, *args)


def run() -> None:
    """Start the HTTP server."""

    port = int(os.getenv("APP_PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), ChessGuardRequestHandler)
    print(f"ChessGuard placeholder dev server running at http://localhost:{port}")
    print("Press CTRL+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
