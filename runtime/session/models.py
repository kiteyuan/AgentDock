"""Session models — conversation state and cancel tokens."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turn:
    role: str
    text: str
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str
    device_id: str
    device_type: str = "unknown"
    agent_id: str | None = None
    tts_id: str | None = None
    tts_model: str | None = None
    created_at: float = field(default_factory=time.time)
    context: list[dict[str, Any]] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def add_turn(self, role: str, text: str) -> None:
        self.context.append({"role": role, "text": text, "ts": time.time()})

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def reset_cancel(self) -> None:
        self.cancel_event = asyncio.Event()

    def device_info(self) -> dict[str, Any]:
        return {"id": self.device_id, "type": self.device_type}
