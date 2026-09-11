"""Resolve the shared Agent workspace directory from config."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def repo_root() -> Path:
    """AgentDock repository root (parent of the ``runtime`` package)."""
    return Path(__file__).resolve().parent.parent


def resolve_workspace(cfg: dict[str, Any] | None = None, *, ensure: bool = False) -> Path:
    """
    Absolute workspace path.

    Config::

        workspace:
          root: "workspace"   # relative to repo root, or absolute

    Default: ``<repo>/workspace``.
    """
    ws = (cfg or {}).get("workspace") if isinstance((cfg or {}).get("workspace"), dict) else {}
    raw = (ws or {}).get("root") or "workspace"
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = repo_root() / path
    path = path.resolve()
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path
