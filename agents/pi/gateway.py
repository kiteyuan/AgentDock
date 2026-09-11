#!/usr/bin/env python3
"""
HTTP gateway: AgentDock Agent Protocol ↔ Pi Coding Agent (--mode json).

  python agents/pi/gateway.py
  → http://127.0.0.1:9000/v1/agent/run

Requires: npm deps in agents/pi (npx pi).

Env:
  PI_GATEWAY_PORT=9001
  PI_CWD=E:\\path\\to\\project   # working directory for tools/files (default: agents/pi)
  PI_NO_TOOLS=1
  PI_NO_SESSION=1               # opt out: ephemeral turns (old behavior)
  PI_SESSION_DIR=...            # Pi session files (default: agents/pi/.agentdock-sessions)
  PI_SESSION_KEY=device         # device (default) | session — what keys Pi --session-id
  PI_APPEND_SYSTEM_PROMPT=...   # append voice style prompt (default: agents/pi/voice_prompt.txt)
  PI_SYSTEM_PROMPT=...          # replace system prompt entirely (path or literal)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROTOCOL = "agentdock.agent/1.0"
HOST = os.environ.get("PI_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("PI_GATEWAY_PORT", "9000"))
HERE = Path(__file__).resolve().parent
# Project workspace for tools/files (default: agents/pi). Override: PI_CWD=/path/to/project
WORK_DIR = Path(os.environ.get("PI_CWD") or os.environ.get("PI_WORKDIR") or HERE).expanduser().resolve()
PROVIDER = os.environ.get("PI_PROVIDER")  # optional override
MODEL = os.environ.get("PI_MODEL")
NO_TOOLS = os.environ.get("PI_NO_TOOLS", "0") == "1"
# Default: reuse Pi session files keyed by AgentDock session_id.
# Set PI_NO_SESSION=1 to restore one-shot (--no-session) turns.
NO_SESSION = os.environ.get("PI_NO_SESSION", "0") == "1"
SESSION_DIR = Path(
    os.environ.get("PI_SESSION_DIR") or (HERE / ".agentdock-sessions")
).expanduser().resolve()
# Key Pi memory by stable device id (survives WS reconnect). Use "session" for WS-scoped.
SESSION_KEY = (os.environ.get("PI_SESSION_KEY") or "device").strip().lower()

# Voice / short-reply system prompt (appended to Pi's default). Override with
# PI_APPEND_SYSTEM_PROMPT=path|text  or PI_SYSTEM_PROMPT=... to replace entirely.
_DEFAULT_VOICE_PROMPT = (
    "你是通过麦克风/扬声器使用的快捷终端助手，回复会被 TTS 直接读给用户听。"
    "尽量简短口语化；纯文本不要 Markdown；先说结论。"
)


def _load_prompt_text(raw: str | None, *, fallback: str) -> str:
    if not raw:
        return fallback
    raw = raw.strip()
    if not raw:
        return fallback
    path = Path(raw).expanduser()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip() or fallback
    return raw


def _system_prompt_args() -> list[str]:
    """CLI flags for system prompt injection."""
    replace = os.environ.get("PI_SYSTEM_PROMPT")
    if replace is not None and replace.strip() != "":
        text = _load_prompt_text(replace, fallback=_DEFAULT_VOICE_PROMPT)
        return ["--system-prompt", text] if text else []

    default_file = HERE / "voice_prompt.txt"
    default = (
        default_file.read_text(encoding="utf-8").strip()
        if default_file.is_file()
        else _DEFAULT_VOICE_PROMPT
    )
    append = os.environ.get("PI_APPEND_SYSTEM_PROMPT")
    text = _load_prompt_text(append, fallback=default) if append is not None else default
    return ["--append-system-prompt", text] if text else []


def _resolve_pi_cmd() -> list[str]:
    """Return argv prefix that launches `pi` on this machine."""
    override = os.environ.get("PI_BIN")
    if override:
        # Allow: PI_BIN="node path/to/cli.js" style via shlex? keep simple single path or node+script
        return [override]

    cli_candidates = [
        HERE
        / "node_modules"
        / "@earendil-works"
        / "pi-coding-agent"
        / "dist"
        / "bundle"
        / "cli.js",
        HERE
        / "node_modules"
        / "@earendil-works"
        / "pi-coding-agent"
        / "dist"
        / "cli.js",
    ]
    import shutil

    node = shutil.which("node") or shutil.which("node.exe")
    for cli in cli_candidates:
        if cli.is_file() and node:
            return [node, str(cli)]

    for name in ("pi.cmd", "pi.exe", "pi"):
        local = HERE / "node_modules" / ".bin" / name
        if local.is_file():
            # .cmd needs shell on Windows; prefer node+cli.js above
            return [str(local)]

    for name in ("pi.cmd", "pi", "npx.cmd", "npx"):
        found = shutil.which(name)
        if not found:
            continue
        if name.startswith("npx"):
            return [found, "--yes", "pi"]
        return [found]

    raise FileNotFoundError(
        "pi not found; run: cd agents/pi && npm install "
        "(or set PI_BIN / ensure node is on PATH)"
    )


def _event(etype: str, session_id: str, **payload: object) -> dict:
    return {
        "type": etype,
        "id": uuid.uuid4().hex[:12],
        "ts": time.time(),
        "payload": {"session_id": session_id, **payload},
    }


def _text_from_message(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _safe_session_id(session_id: str) -> str:
    """Filesystem-safe id for Pi --session-id (create-if-missing)."""
    cleaned = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return cleaned[:64] or uuid.uuid4().hex[:12]


def _pi_memory_key(*, session_id: str, device_id: str | None) -> str:
    """Choose Pi session file key. Prefer device so reconnect keeps memory."""
    if NO_SESSION:
        return session_id
    mode = SESSION_KEY
    did = (device_id or "").strip()
    if mode == "session" or not did:
        return _safe_session_id(session_id)
    # Prefix avoids colliding with short AgentDock WS session ids.
    return _safe_session_id(f"dev-{did}")


def _build_pi_cmd(prompt: str, *, pi_key: str) -> list[str]:
    cmd = [*_resolve_pi_cmd(), "--mode", "json", "--print"]
    if NO_SESSION:
        cmd.append("--no-session")
    else:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        cmd += [
            "--session-dir",
            str(SESSION_DIR),
            "--session-id",
            pi_key,
        ]
    if PROVIDER:
        cmd += ["--provider", PROVIDER]
    if MODEL:
        cmd += ["--model", MODEL]
    if NO_TOOLS:
        cmd += ["--no-tools"]
    cmd += _system_prompt_args()
    cmd.append(prompt)
    return cmd


def run_pi_turn(
    session_id: str,
    text: str,
    write_event,
    *,
    device_id: str | None = None,
) -> None:
    pi_key = _pi_memory_key(session_id=session_id, device_id=device_id)
    cmd = _build_pi_cmd(text, pi_key=pi_key)
    sid_note = "ephemeral" if NO_SESSION else pi_key
    write_event(
        _event(
            "agent.thinking",
            session_id,
            content=f"pi[{sid_note}]: {' '.join(cmd[:6])} …",
        )
    )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(WORK_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError as exc:
        write_event(_event("agent.error", session_id, content=f"cannot start pi: {exc}"))
        return

    assistant_text = ""
    saw_done = False
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = raw.get("type")
        if et == "agent_start":
            write_event(_event("agent.start", session_id))
        elif et == "message_update":
            ame = raw.get("assistantMessageEvent") or {}
            if ame.get("type") == "text_delta" and ame.get("delta"):
                # progress only — final speak text comes from message_end
                pass
            elif ame.get("type") == "thinking_delta" and ame.get("delta"):
                write_event(
                    _event("agent.thinking", session_id, content=str(ame.get("delta"))[:200])
                )
        elif et == "tool_execution_start":
            write_event(
                _event(
                    "agent.tool_call",
                    session_id,
                    tool=str(raw.get("toolName") or raw.get("tool") or "tool"),
                    args=raw.get("args") if isinstance(raw.get("args"), dict) else {},
                )
            )
        elif et == "tool_execution_end":
            write_event(
                _event(
                    "agent.tool_result",
                    session_id,
                    tool=str(raw.get("toolName") or raw.get("tool") or "tool"),
                    status="error" if raw.get("isError") else "success",
                    content=str(raw.get("result") or raw.get("error") or "")[:500],
                )
            )
        elif et == "message_end":
            msg = raw.get("message") or {}
            if msg.get("role") == "assistant":
                assistant_text = _text_from_message(msg)
                if assistant_text:
                    write_event(
                        _event(
                            "agent.message",
                            session_id,
                            content=assistant_text,
                            speak=True,
                        )
                    )
        elif et == "agent_end":
            if not assistant_text:
                # fallback: last assistant in messages list
                for m in reversed(raw.get("messages") or []):
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        assistant_text = _text_from_message(m)
                        if assistant_text:
                            write_event(
                                _event(
                                    "agent.message",
                                    session_id,
                                    content=assistant_text,
                                    speak=True,
                                )
                            )
                        break
            write_event(_event("agent.done", session_id))
            saw_done = True
        elif et == "error":
            write_event(
                _event(
                    "agent.error",
                    session_id,
                    content=str(raw.get("message") or raw.get("error") or raw),
                )
            )
            saw_done = True

    stderr = ""
    if proc.stderr:
        stderr = proc.stderr.read()
    code = proc.wait(timeout=10)
    if not saw_done:
        if code != 0:
            write_event(
                _event(
                    "agent.error",
                    session_id,
                    content=(stderr or f"pi exited {code}")[:800],
                )
            )
        else:
            if assistant_text:
                write_event(
                    _event("agent.message", session_id, content=assistant_text, speak=True)
                )
            write_event(_event("agent.done", session_id))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[pi-gateway] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/v1/agent":
            body = {
                "protocol": PROTOCOL,
                "id": "pi",
                "name": "Pi Coding Agent",
                "capabilities": ["coding", "bash", "filesystem"],
                "description": "Gateway over @earendil-works/pi-coding-agent (--mode json, Pi memory by device_id)",
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
        length = int(self.headers.get("Content-Length", "0"))
        raw_in = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw_in.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return

        path = self.path.rstrip("/")
        if path == "/v1/agent/cancel":
            out = json.dumps(
                {
                    "ok": True,
                    "note": "print-mode cancel is best-effort; Pi session file is kept for reuse",
                }
            ).encode()
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
        device = req.get("device") if isinstance(req.get("device"), dict) else {}
        device_id = str(device.get("id") or device.get("device_id") or "").strip() or None

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("X-AgentDock-Protocol", PROTOCOL)
        self.send_header("Connection", "close")
        self.end_headers()

        def write_event(obj: dict) -> None:
            line = (json.dumps(obj, ensure_ascii=False) + "\n").encode()
            self.wfile.write(line)
            self.wfile.flush()

        try:
            run_pi_turn(sid, text, write_event, device_id=device_id)
        except Exception as exc:  # noqa: BLE001
            write_event(_event("agent.error", sid, content=str(exc)))


def main() -> None:
    bin_dir = HERE / "node_modules" / ".bin"
    if bin_dir.is_dir():
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

    try:
        prefix = _resolve_pi_cmd()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    # Line-buffer logs when piped
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    if not WORK_DIR.is_dir():
        print(f"PI_CWD is not a directory: {WORK_DIR}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Pi Agent gateway on http://{HOST}:{PORT}", flush=True)
    print(f"  cwd={WORK_DIR}", flush=True)
    print(f"  pi cmd: {prefix}", flush=True)
    if NO_SESSION:
        print("  sessions: ephemeral (--no-session)", flush=True)
    else:
        print(
            f"  sessions: key={SESSION_KEY} under {SESSION_DIR}",
            flush=True,
        )
    sp = _system_prompt_args()
    if sp:
        kind = "replace" if sp[0] == "--system-prompt" else "append"
        preview = (sp[1][:60] + "…") if len(sp[1]) > 60 else sp[1]
        print(f"  system_prompt ({kind}): {preview}", flush=True)
    if PROVIDER:
        print(f"  provider={PROVIDER} model={MODEL or '(default)'}", flush=True)
    if NO_TOOLS:
        print("  flags: --no-tools", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
