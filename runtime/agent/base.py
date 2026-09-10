"""AgentAdapter — Input → async Agent Event Stream."""

from __future__ import annotations

from abc import ABC, abstractmethod

from runtime.protocol.agent import AgentEventStream, AgentInfo, AgentRequest


class AgentAdapter(ABC):
    @property
    @abstractmethod
    def info(self) -> AgentInfo: ...

    @abstractmethod
    async def run(self, request: AgentRequest) -> AgentEventStream:
        """Yield AgentEvent items until done / cancel / error."""
        ...
