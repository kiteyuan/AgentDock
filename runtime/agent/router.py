"""Agent Router — select which adapter handles a request."""

from __future__ import annotations

from runtime.agent.base import AgentAdapter
from runtime.agent.registry import AgentRegistry
from runtime.security.permissions import PermissionGuard


class AgentRouter:
    """Skeleton router: default agent, or explicit agent_id."""

    def __init__(
        self,
        registry: AgentRegistry,
        default_agent_id: str,
        permissions: PermissionGuard | None = None,
    ) -> None:
        self.registry = registry
        self.default_agent_id = default_agent_id
        self.permissions = permissions or PermissionGuard()

    def resolve(self, *, device_id: str, agent_id: str | None = None) -> AgentAdapter:
        target = agent_id or self.default_agent_id
        if not self.permissions.allow_agent(device_id, target):
            raise PermissionError(self.permissions.deny_reason(device_id, target))
        adapter = self.registry.get(target)
        if adapter is None:
            raise KeyError(f"unknown agent: {target}")
        return adapter
