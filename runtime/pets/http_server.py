"""HTTP server for pet assets: GET /pets/catalog.json, GET /pets/<id>/..."""

from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from loguru import logger

from runtime.pets import list_pets, load_catalog, resolve_asset


class _PetHandler(BaseHTTPRequestHandler):
    pets_root: Path = Path("pets")

    def log_message(self, fmt: str, *args: object) -> None:
        logger.debug("[pets-http] " + (fmt % args))

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "public, max-age=86400")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path or "/")
        if path in ("/pets", "/pets/"):
            path = "/pets/catalog.json"

        if path == "/pets/catalog.json":
            body = json.dumps(load_catalog(self.pets_root), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/pets/"):
            rel = path[len("/pets/") :]
            asset = resolve_asset(self.pets_root, rel)
            if asset is None:
                self.send_error(404, "pet asset not found")
                return
            data = asset.read_bytes()
            ctype = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path in ("/", "/health"):
            pets, default = list_pets(self.pets_root)
            body = json.dumps(
                {"ok": True, "pets": len(pets), "default": default},
                ensure_ascii=False,
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)


def start_pets_http_server(
    *,
    host: str,
    port: int,
    pets_root: Path,
) -> ThreadingHTTPServer:
    _PetHandler.pets_root = pets_root
    httpd = ThreadingHTTPServer((host, port), _PetHandler)
    thread = threading.Thread(target=httpd.serve_forever, name="pets-http", daemon=True)
    thread.start()
    pets, default = list_pets(pets_root)
    logger.info(
        "Pet assets HTTP on http://{}:{}/pets/ ({} packs, default={})",
        host,
        port,
        len(pets),
        default,
    )
    return httpd


def build_assets_base_url(
    *,
    host_hint: str | None,
    port: int,
    advertise_url: str | None = None,
    assets_url: str | None = None,
) -> str:
    """Public base URL clients use to download pet files (…/pets)."""
    if assets_url:
        return str(assets_url).rstrip("/")
    if advertise_url:
        u = str(advertise_url).strip()
        if u.startswith("wss://"):
            u = "https://" + u[len("wss://") :]
        elif u.startswith("ws://"):
            u = "http://" + u[len("ws://") :]
        parsed = urlparse(u)
        hostname = parsed.hostname or "127.0.0.1"
        scheme = parsed.scheme or "http"
        return f"{scheme}://{hostname}:{port}/pets"
    hint = (host_hint or "127.0.0.1").strip()
    if hint in ("0.0.0.0", "::", "[::]"):
        hint = "127.0.0.1"
    return f"http://{hint}:{port}/pets"
