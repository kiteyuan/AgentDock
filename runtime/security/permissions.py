"""Permission skeleton — Session → Agent access checks."""

from __future__ import annotations


class PermissionGuard:
    """Placeholder: currently allows all agent access."""

    def allow_agent(self, device_id: str, agent_id: str) -> bool:
        return True

    def deny_reason(self, device_id: str, agent_id: str) -> str:
        return f"device {device_id} is not allowed to use agent {agent_id}"
