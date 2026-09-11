"""Serve the unified Web UI (desktop preview over HTTP)."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Avoid sticky JS/CSS cache while iterating on the UI."""

    def end_headers(self) -> None:
        path = (self.path or "").split("?", 1)[0].lower()
        if path.endswith((".js", ".css", ".html")) or path in ("", "/"):
            self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentDock Web UI")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    handler = functools.partial(NoCacheHandler, directory=str(ROOT))
    httpd = socketserver.TCPServer(("0.0.0.0", args.port), handler)

    url = f"http://127.0.0.1:{args.port}/"
    print(f"AgentDock Web UI → {url}")
    print("Desktop preview only. Phone: use clients/mobile (Flutter).")
    if not args.no_open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
