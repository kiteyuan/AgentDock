"""Build AgentAdapter instances from config (built-in + import path plugins)."""

from __future__ import annotations

import importlib
from typing import Any

from runtime.agent.base import AgentAdapter


def create_agent(agent_id: str, cfg: dict[str, Any]) -> AgentAdapter:
    """
    Supported types:
      - mock / echo / http
      - import: "my_pkg.module:ClassName"  (plugin path)
    """
    atype = cfg.get("type", agent_id)

    if atype == "mock":
        from runtime.agent.adapters.mock import MockAgent

        return MockAgent()
    if atype == "echo":
        from runtime.agent.adapters.echo import EchoAgent

        return EchoAgent()
    if atype == "http":
        from runtime.agent.adapters.http import HTTPAgent

        return HTTPAgent(
            url=cfg["url"],
            agent_id=agent_id,
            name=cfg.get("name", "HTTP Agent"),
            capabilities=list(cfg.get("capabilities") or ["http"]),
            mode=cfg.get("mode", "auto"),  # stream | events | text | auto
            headers=dict(cfg.get("headers") or {}),
            auth_token=cfg.get("auth_token"),
            timeout=float(cfg.get("timeout", 120)),
            cancel_url=cfg.get("cancel_url"),
            description=cfg.get("description"),
        )
    if atype == "import" or ":" in str(atype):
        path = cfg.get("path") or atype
        return _load_import(path, cfg, agent_id)

    raise ValueError(f"unknown agent type: {atype}")


def _load_import(path: str, cfg: dict[str, Any], agent_id: str) -> AgentAdapter:
    """Load `package.module:ClassName` and instantiate with remaining cfg."""
    if ":" not in path:
        raise ValueError(f"import path must be 'module:Class', got {path!r}")
    mod_name, cls_name = path.rsplit(":", 1)
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    kwargs = {k: v for k, v in cfg.items() if k not in ("type", "path")}
    kwargs.setdefault("agent_id", agent_id)
    obj = cls(**kwargs)
    if not isinstance(obj, AgentAdapter):
        raise TypeError(f"{path} did not return AgentAdapter")
    return obj
