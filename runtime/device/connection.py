"""Per-connection device state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import websockets

from runtime.session.models import Session


@dataclass
class DeviceConnection:
    ws: websockets.WebSocketServerProtocol
    device_id: str | None = None
    device_type: str = "unknown"
    session: Session | None = None
    audio_buf: bytearray = field(default_factory=bytearray)

    async def send(self, data: str | bytes) -> None:
        await self.ws.send(data)

    async def send_json(self, obj: dict[str, Any]) -> None:
        import json

        await self.ws.send(json.dumps(obj))
