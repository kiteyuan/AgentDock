"""Serve the unified Web UI over HTTPS (LAN mic requires secure context)."""

from __future__ import annotations

import argparse
import functools
import http.server
import ssl
import socketserver
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CERT_DIR = REPO / "certs"


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Avoid sticky JS/CSS cache while iterating on the UI."""

    def end_headers(self) -> None:
        path = (self.path or "").split("?", 1)[0].lower()
        if path.endswith((".js", ".css", ".html")) or path in ("", "/"):
            self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = (self.path or "").split("?", 1)[0]
        if path in ("/ca.pem", "/cert.pem"):
            name = path.lstrip("/")
            src = CERT_DIR / name
            if not src.is_file():
                self.send_error(404, f"{name} missing — run certs/ensure.py")
                return
            data = src.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-pem-file")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentDock Web UI")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument(
        "--https",
        action="store_true",
        help="Serve HTTPS (needed for mic on http://LAN-IP). Default is plain HTTP.",
    )
    args = parser.parse_args()

    handler = functools.partial(NoCacheHandler, directory=str(ROOT))
    httpd = socketserver.TCPServer(("0.0.0.0", args.port), handler)

    scheme = "http"
    if args.https:
        sys.path.insert(0, str(REPO))
        from certs.ensure import ensure_certs

        ca_path, cert_path, key_path = ensure_certs(CERT_DIR)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
        print(f"TLS cert: {cert_path}")
        print(f"Install CA on phone: {ca_path}  (or open {scheme}://<LAN-IP>:{args.port}/ca.pem)")

    url = f"{scheme}://127.0.0.1:{args.port}/"
    print(f"AgentDock Web UI → {url}")
    if scheme == "https":
        print("Phone: open https://<this-PC-LAN-IP>:8090  (trust CA first), WS use wss://<IP>:8765")
    else:
        print("LAN tip: mic needs HTTPS — restart with: python clients/web/serve.py --https")
    if not args.no_open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
