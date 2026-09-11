"""Load Pi client config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | None = None) -> dict[str, Any]:
    candidates = []
    if path:
        candidates.append(Path(path))
    here = Path(__file__).resolve().parent.parent
    candidates.extend([here / "config.yaml", Path("config.yaml")])
    for p in candidates:
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}
