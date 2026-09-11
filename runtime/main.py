"""AgentDock Runtime entry point."""

from __future__ import annotations

import asyncio
import sys

from runtime.config import load_config
from runtime.runtime import Runtime


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config(config_path)
    runtime = Runtime(cfg)
    asyncio.run(runtime.start())


if __name__ == "__main__":
    main()
