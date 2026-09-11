"""Workspace path resolution."""

from __future__ import annotations

from pathlib import Path

from runtime.workspace import repo_root, resolve_workspace


def test_default_workspace_under_repo() -> None:
    path = resolve_workspace({})
    assert path == (repo_root() / "workspace").resolve()


def test_absolute_workspace() -> None:
    abs_path = Path("C:/tmp/agentdock-ws").resolve() if Path("C:/").exists() else Path("/tmp/agentdock-ws")
    path = resolve_workspace({"workspace": {"root": str(abs_path)}})
    assert path == abs_path


def test_relative_workspace() -> None:
    path = resolve_workspace({"workspace": {"root": "workspace"}})
    assert path == (repo_root() / "workspace").resolve()
