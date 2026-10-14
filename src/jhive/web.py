"""Serve the local JHive dashboard without connecting to a broker or market feed."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class DashboardHandler(BaseHTTPRequestHandler):
    """Serve the bundled dashboard from a local-only development server."""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        assets = {
            "/": ("dashboard.html", "text/html; charset=utf-8"),
            "/index.html": ("dashboard.html", "text/html; charset=utf-8"),
            "/jhive-logo.png": ("jhive-logo.png", "image/png"),
        }
        asset = assets.get(self.path)
        if asset is None:
            self.send_error(404)
            return
        filename, content_type = asset
        body = (Path(__file__).parent / "static" / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"JHive dashboard: {args[0] if args else fmt}")


def main() -> None:
    """Start the dashboard on loopback so it is only available on this computer."""
    parser = argparse.ArgumentParser(description="Run the local JHive demo dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"JHive demo dashboard running at http://{args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping JHive dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
