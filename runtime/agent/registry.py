"""Agent Registry — discovery of available adapters."""

from __future__ import annotations

from runtime.agent.base import AgentAdapter
from runtime.protocol.agent import AgentInfo


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentAdapter] = {}

    def register(self, adapter: AgentAdapter) -> None:
        self._agents[adapter.info.id] = adapter

    def get(self, agent_id: str) -> AgentAdapter | None:
        return self._agents.get(agent_id)

    def list(self) -> list[AgentInfo]:
        return [a.info for a in self._agents.values()]

    def list_dicts(self) -> list[dict]:
        return [info.model_dump() for info in self.list()]

    def ids(self) -> list[str]:
        return list(self._agents.keys())
