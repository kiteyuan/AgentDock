"""Configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger


def load_config(path: str | None = None) -> dict[str, Any]:
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))

    cwd = Path.cwd()
    for folder in [cwd, *cwd.parents]:
        candidates.append(folder / "config.yaml")
        candidates.append(folder / "config.yml")
        if folder.name == "AgentDock" or (folder / "pyproject.toml").exists():
            break

    # repo root next to the installed package: .../AgentDock/runtime/config.py
    pkg_root = Path(__file__).resolve().parent.parent
    candidates.append(pkg_root / "config.yaml")
    candidates.append(pkg_root / "config.yml")

    seen: set[Path] = set()
    for p in candidates:
        try:
            resolved = p.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
        logger.info("Loaded config: {}", resolved)
        return data
    logger.warning("No config file found, using defaults")
    return {}
