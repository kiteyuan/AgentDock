"""Event bus — push AgentEvents to a Device connection sender."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from runtime.protocol.agent import AgentEvent

SendFn = Callable[[str | bytes], Awaitable[None]]


class EventBus:
    """Forwards agent events to the connected device as wire JSON."""

    def __init__(self, send: SendFn) -> None:
        self._send = send

    async def publish(self, event: AgentEvent) -> None:
        await self._send(json.dumps(event.to_wire()))
