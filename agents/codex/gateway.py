#!/usr/bin/env python3
"""
HTTP gateway: AgentDock Agent Protocol ↔ OpenAI Codex CLI (`codex exec --json`).

  python agents/codex/gateway.py
  → http://127.0.0.1:9002/v1/agent/run

Requires: `codex` on PATH (https://github.com/openai/codex) and auth configured.

Env:
  CODEX_GATEWAY_PORT=9002
  CODEX_CWD=...                 # fallback cwd (default: <repo>/workspace)
  CODEX_BIN=codex
  CODEX_SANDBOX=workspace-write # or read-only / danger-full-access
  CODEX_MODEL=...
  CODEX_SKIP_GIT_CHECK=1        # default 1 (workspace may not be a git repo)
  CODEX_APPEND_SYSTEM_PROMPT=... / CODEX_SYSTEM_PROMPT=...
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_AGENTS = _HERE.parent
if str(_AGENTS) not in sys.path:
    sys.path.insert(0, str(_AGENTS))

from common import (  # noqa: E402
    PROTOCOL,
    device_id_of,
    event,
    fallback_work_dir,
    make_write_event,
    read_json_request,
    repo_root_from,
    resolve_request_cwd,
    send_json,
    voice_prompt,
    which,
    write_ndjson_headers,
)

HOST = os.environ.get("CODEX_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("CODEX_GATEWAY_PORT", "9002"))
HERE = _HERE
REPO_ROOT = repo_root_from(HERE)
FALLBACK_WORK_DIR = fallback_work_dir(REPO_ROOT, env_cwd="CODEX_CWD", env_workdir="CODEX_WORKDIR")
BIN = os.environ.get("CODEX_BIN") or which("codex") or "codex"
SANDBOX = os.environ.get("CODEX_SANDBOX", "workspace-write")
MODEL = os.environ.get("CODEX_MODEL")
SKIP_GIT = os.environ.get("CODEX_SKIP_GIT_CHECK", "1") == "1"

_DEFAULT_VOICE = (
    "你是通过麦克风/扬声器使用的快捷终端助手，回复会被 TTS 朗读。"
    "尽量简短口语化；纯文本不要 Markdown；先说结论。"
)


def _system_prompt() -> str:
    return voice_prompt(
        HERE,
        env_append="CODEX_APPEND_SYSTEM_PROMPT",
        env_replace="CODEX_SYSTEM_PROMPT",
        default=_DEFAULT_VOICE,
    )


def _build_cmd(prompt: str, *, cwd: Path) -> list[str]:
    # Flag forms match docs: `codex exec --json --sandbox workspace-write --cd <dir>`
    cmd = [BIN, "exec", "--json", "--sandbox", SANDBOX, "--cd", str(cwd)]
    if SKIP_GIT:
        cmd.append("--skip-git-repo-check")
    if MODEL:
        cmd += ["--model", MODEL]
    # Codex has no --append-system-prompt; prefix voice style into the user prompt.
    sp = _system_prompt().strip()
    full = f"{sp}\n\n用户请求：{prompt}" if sp else prompt
    cmd.append(full)
    return cmd


def _item_text(item: dict) -> str:
    for key in ("text", "content", "message", "result"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def run_codex_turn(session_id: str, text: str, write_event, *, cwd: Path) -> None:
    if not cwd.is_dir():
        write_event(event("agent.error", session_id, content=f"workspace is not a directory: {cwd}"))
        return
    cmd = _build_cmd(text, cwd=cwd)
    write_event(
        event(
            "agent.thinking",
            session_id,
            content=f"codex cwd={cwd}: {' '.join(cmd[:6])} …",
        )
    )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError as exc:
        write_event(event("agent.error", session_id, content=f"cannot start codex: {exc}"))
        return

    assistant_text = ""
    saw_done = False
    assert proc.stdout is not None
    import json

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = str(raw.get("type") or "")
        if et == "thread.started":
            write_event(event("agent.start", session_id))
        elif et == "turn.started":
            write_event(event("agent.thinking", session_id, content="codex turn started"))
        elif et in ("item.started", "item.updated", "item.completed"):
            item = raw.get("item") if isinstance(raw.get("item"), dict) else {}
            itype = str(item.get("type") or "")
            if itype in ("command_execution", "command", "mcp_tool_call", "file_change"):
                write_event(
                    event(
                        "agent.tool_call" if et != "item.completed" else "agent.tool_result",
                        session_id,
                        tool=itype,
                        status="success" if et == "item.completed" else None,
                        content=_item_text(item)[:500] or None,
                        args={k: item.get(k) for k in ("command", "path", "server") if k in item},
                    )
                )
            elif itype in ("agent_message", "message", "agent_message_delta"):
                chunk = _item_text(item)
                if chunk:
                    assistant_text = chunk
                    if et == "item.completed":
                        write_event(
                            event("agent.message", session_id, content=chunk, speak=True)
                        )
            elif itype in ("reasoning", "plan_update"):
                note = _item_text(item)
                if note:
                    write_event(event("agent.thinking", session_id, content=note[:300]))
        elif et == "turn.completed":
            if assistant_text:
                # already emitted on item.completed; still ensure done
                pass
            write_event(event("agent.done", session_id))
            saw_done = True
        elif et in ("turn.failed", "error"):
            write_event(
                event(
                    "agent.error",
                    session_id,
                    content=str(raw.get("error") or raw.get("message") or raw)[:800],
                )
            )
            saw_done = True

    stderr = proc.stderr.read() if proc.stderr else ""
    code = proc.wait(timeout=30)
    if not saw_done:
        if code != 0:
            write_event(
                event(
                    "agent.error",
                    session_id,
                    content=(stderr or f"codex exited {code}")[:800],
                )
            )
        else:
            if assistant_text:
                write_event(event("agent.message", session_id, content=assistant_text, speak=True))
            write_event(event("agent.done", session_id))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[codex-gateway] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/v1/agent":
            send_json(
                self,
                {
                    "protocol": PROTOCOL,
                    "id": "codex",
                    "name": "OpenAI Codex",
                    "capabilities": ["coding", "bash", "filesystem"],
                    "description": "Gateway over `codex exec --json`",
                },
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        req = read_json_request(self)
        if req is None:
            return
        path = self.path.rstrip("/")
        if path == "/v1/agent/cancel":
            send_json(
                self,
                {"ok": True, "note": "codex exec cancel is best-effort (process already running)"},
            )
            return
        if path != "/v1/agent/run":
            self.send_error(404)
            return

        sid = str(req.get("session_id") or uuid.uuid4().hex[:12])
        text = str(req.get("text") or "")
        cwd = resolve_request_cwd(req, FALLBACK_WORK_DIR)
        _ = device_id_of(req)  # reserved for future session resume

        write_ndjson_headers(self)
        write_event = make_write_event(self)
        try:
            run_codex_turn(sid, text, write_event, cwd=cwd)
        except Exception as exc:  # noqa: BLE001
            write_event(event("agent.error", sid, content=str(exc)))


def main() -> None:
    if which(BIN) is None and not Path(BIN).exists():
        print(
            f"codex not found ({BIN!r}); install OpenAI Codex CLI and ensure it is on PATH",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not FALLBACK_WORK_DIR.is_dir():
        FALLBACK_WORK_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Codex gateway on http://{HOST}:{PORT}", flush=True)
    print(f"  fallback cwd={FALLBACK_WORK_DIR} (request.workspace overrides)", flush=True)
    print(f"  bin={BIN} sandbox={SANDBOX}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
