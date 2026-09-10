#!/usr/bin/env python3
"""
Reference public Agent — AgentDock Agent Protocol v1.0.

Run:
  python agents/demo/server.py
  # listens on http://127.0.0.1:8080

Endpoints:
  GET  /v1/agent
  POST /v1/agent/run      (NDJSON stream)
  POST /v1/agent/cancel

Point AgentDock config at:
  url: "http://127.0.0.1:8080/v1/agent/run"
  mode: stream
  auth_token: "dev-token"   # optional; set AGENT_TOKEN to require it
"""

from __future__ import annotations

import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL = "agentdock.agent/1.0"
HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGENT_PORT", "8080"))
TOKEN = os.environ.get("AGENT_TOKEN", "")  # empty = auth optional
_cancelled: set[str] = set()


def _event(etype: str, session_id: str, **payload: object) -> dict:
    body = {"session_id": session_id, **payload}
    return {
        "type": etype,
        "id": uuid.uuid4().hex[:12],
        "ts": time.time(),
        "payload": body,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[http-agent] {self.address_string()} {fmt % args}")

    def _unauthorized(self) -> bool:
        if not TOKEN:
            return False
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {TOKEN}":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}')
            return True
        return False

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/v1/agent":
            body = {
                "protocol": PROTOCOL,
                "id": "demo",
                "name": "Reference HTTP Agent",
                "capabilities": ["demo", "general"],
                "description": "Compliant sample for AgentDock public Agent Protocol",
            }
            raw = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self._unauthorized():
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return

        path = self.path.rstrip("/")
        if path == "/v1/agent/cancel":
            sid = str(req.get("session_id") or "")
            if sid:
                _cancelled.add(sid)
            out = json.dumps({"ok": True, "session_id": sid}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return

        if path != "/v1/agent/run":
            self.send_error(404)
            return

        sid = str(req.get("session_id") or uuid.uuid4().hex[:12])
        text = str(req.get("text") or "")
        _cancelled.discard(sid)

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("X-AgentDock-Protocol", PROTOCOL)
        self.send_header("Connection", "close")
        self.end_headers()

        def write_event(obj: dict) -> None:
            line = (json.dumps(obj, ensure_ascii=False) + "\n").encode()
            self.wfile.write(line)
            self.wfile.flush()

        events = [
            _event("agent.thinking", sid, content=f"收到：「{text}」"),
            _event(
                "agent.tool_call",
                sid,
                tool="demo.echo",
                args={"text": text},
            ),
            _event(
                "agent.tool_result",
                sid,
                tool="demo.echo",
                status="success",
                content="ok",
                data={"echo": text},
            ),
            # Display-only note (no TTS)
            _event(
                "agent.message",
                sid,
                content=f"[log] processed {len(text)} chars",
                speak=False,
            ),
            # Spoken reply (TTS)
            _event(
                "agent.message",
                sid,
                content=f"已经处理完：「{text}」",
                speak=True,
            ),
            _event("agent.done", sid),
        ]

        for ev in events:
            if sid in _cancelled:
                write_event(_event("agent.cancel", sid, content="cancelled"))
                break
            write_event(ev)
            time.sleep(0.05)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Reference Agent Protocol server on http://{HOST}:{PORT}")
    print(f"  GET  /v1/agent")
    print(f"  POST /v1/agent/run")
    print(f"  POST /v1/agent/cancel")
    if TOKEN:
        print("  auth: Bearer required (AGENT_TOKEN)")
    else:
        print("  auth: optional (set AGENT_TOKEN to require)")
    server.serve_forever()


if __name__ == "__main__":
    main()
