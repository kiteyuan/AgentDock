#!/usr/bin/env python3
"""Probe an Agent Protocol endpoint (install / link smoke test).

Usage:
  python agents/check_link.py --url http://127.0.0.1:8080/v1/agent/run
  python agents/check_link.py --url http://127.0.0.1:8080/v1/agent/run --text "你好" --token secret
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running without install: repo root on path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime.agent.adapters.http import HTTPAgent
from runtime.protocol.agent import AgentEventType, AgentRequest


async def probe(url: str, text: str, token: str | None, timeout: float) -> int:
    agent = HTTPAgent(
        url,
        agent_id="probe",
        name="link-check",
        mode="stream",
        auth_token=token,
        timeout=timeout,
    )
    req = AgentRequest(session_id="link-check", text=text)
    print(f"POST {url}")
    print(f"text: {text!r}")
    print("--- events ---")
    saw_message = False
    saw_terminal = False
    try:
        async for ev in agent.run(req):
            line = ev.type.value
            if ev.content:
                line += f"  {ev.content[:120]}"
            if ev.type == AgentEventType.MESSAGE:
                line += f"  speak={ev.speak}"
                saw_message = True
            if ev.type in (AgentEventType.DONE, AgentEventType.CANCEL, AgentEventType.ERROR):
                saw_terminal = True
            print(line)
            if ev.type == AgentEventType.ERROR:
                print("FAIL: agent.error")
                return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1

    if not saw_message:
        print("WARN: no agent.message (ok if agent only returns tools)")
    if not saw_terminal:
        print("FAIL: no terminal event (done/cancel/error)")
        return 1
    print("--- OK: link looks good ---")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Test Agent Protocol link")
    p.add_argument("--url", required=True, help="Agent run URL, e.g. http://127.0.0.1:8080/v1/agent/run")
    p.add_argument("--text", default="ping from AgentDock check_link")
    p.add_argument("--token", default=None, help="Bearer token (or set via agent auth)")
    p.add_argument("--timeout", type=float, default=60)
    args = p.parse_args()
    raise SystemExit(asyncio.run(probe(args.url, args.text, args.token, args.timeout)))


if __name__ == "__main__":
    main()
