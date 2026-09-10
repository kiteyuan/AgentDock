"""Pi Terminal entry — click to start / click to stop against AgentDock Runtime."""

from __future__ import annotations

import argparse
import asyncio
import sys
import threading
from pathlib import Path

# Allow `python -m device` from clients/pi
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
_SHARED_PARENT = _HERE.parent  # clients/
if str(_SHARED_PARENT) not in sys.path:
    sys.path.insert(0, str(_SHARED_PARENT))

from loguru import logger

from device.config import load_config
from device.display import build_display
from device.input_trigger import build_trigger
from device.network import RuntimeConnection
from device.state import DeviceState


async def main_async(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    display = build_display(cfg.get("display") or {})
    display.show(DeviceState.BOOT)

    audio = cfg.get("audio") or {}
    reconnect = cfg.get("reconnect") or {}
    conn = RuntimeConnection(
        url=cfg.get("runtime_url") or "ws://127.0.0.1:8765",
        device_id=cfg.get("device_id") or "pi-001",
        device_type=cfg.get("device_type") or "pi",
        token=cfg.get("token"),
        tts_id=cfg.get("tts_id"),
        tts_model=cfg.get("tts_model"),
        agent_id=cfg.get("agent_id"),
        display=display,
        sample_rate=int(audio.get("sample_rate", 16000)),
        record_seconds=float(audio.get("record_seconds", 5)),
        heartbeat_seconds=float(cfg.get("heartbeat_seconds", 15)),
        reconnect_retries=int(reconnect.get("retries", 20)),
        reconnect_delay=float(reconnect.get("base_delay", 1.0)),
    )
    trigger = build_trigger(cfg.get("button") or {})

    await conn.connect()
    try:
        while True:
            await trigger.wait_press()
            stop = threading.Event()

            async def _wait_stop() -> None:
                await trigger.wait_press()
                stop.set()

            stopper = asyncio.create_task(_wait_stop())
            try:
                await conn.talk_once(stop)
            except Exception as exc:  # noqa: BLE001
                logger.exception("turn failed: {}", exc)
                display.show(DeviceState.ERROR, str(exc)[:21])
                await asyncio.sleep(1)
                display.show(DeviceState.ONLINE)
            finally:
                stop.set()
                stopper.cancel()
                try:
                    await stopper
                except asyncio.CancelledError:
                    pass
    except KeyboardInterrupt:
        logger.info("bye")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentDock Pi Terminal")
    parser.add_argument("-c", "--config", default=None, help="path to config.yaml")
    args = parser.parse_args()
    asyncio.run(main_async(args.config))


if __name__ == "__main__":
    main()
