"""Echo Agent — minimal event stream."""

from __future__ import annotations

from runtime.agent.base import AgentAdapter
from runtime.protocol.agent import (
    AgentEventStream,
    AgentInfo,
    AgentRequest,
    agent_done,
    agent_message,
    agent_start,
)


class EchoAgent(AgentAdapter):
    @property
    def info(self) -> AgentInfo:
        return AgentInfo(id="echo", name="Echo Agent", capabilities=["echo"])

    async def run(self, request: AgentRequest) -> AgentEventStream:
        yield agent_start(request.session_id)
        yield agent_message(request.session_id, f"Echo: {request.text}")
        yield agent_done(request.session_id)
