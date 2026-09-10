#!/usr/bin/env python3
"""Optional: zip clients/web for desktop/LAN preview (no Runtime)."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("dist/agentdock-web.zip"),
    )
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2] / "clients" / "web"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(root.parent))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
