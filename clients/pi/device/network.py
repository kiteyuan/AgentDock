"""WebSocket runtime connection with reconnect + heartbeat."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import websockets
from loguru import logger
from websockets.exceptions import ConnectionClosed

from device.audio import play_file, record_until_stop, sniff_ext
from device.display import Display
from device.protocol import audio_end, audio_start, device_hello, ping, session_cancel
from device.state import DeviceState

_SHARED = Path(__file__).resolve().parents[2] / "shared"
if str(_SHARED) not in sys.path:
    sys.path.append(str(_SHARED))
from turn_view import TurnView  # noqa: E402


class RuntimeConnection:
    def __init__(
        self,
        *,
        url: str,
        device_id: str,
        device_type: str = "pi",
        token: str | None = None,
        tts_id: str | None = None,
        tts_model: str | None = None,
        agent_id: str | None = None,
        display: Display,
        sample_rate: int = 16000,
        record_seconds: float = 5,
        heartbeat_seconds: float = 15,
        reconnect_retries: int = 20,
        reconnect_delay: float = 1.0,
    ) -> None:
        self.url = url
        self.device_id = device_id
        self.device_type = device_type
        self.token = token
        self.tts_id = tts_id
        self.tts_model = tts_model
        self.agent_id = agent_id
        self.display = display
        self.sample_rate = sample_rate
        self.record_seconds = record_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.reconnect_retries = reconnect_retries
        self.reconnect_delay = reconnect_delay
        self._ws: Any = None
        self.session_id: str | None = None
        self._hb: asyncio.Task | None = None
        self._view = TurnView(print=lambda s: logger.info("{}", s))

    def _set(self, state: DeviceState, line: str = "") -> None:
        self.display.show(state, line)

    async def connect(self) -> None:
        self._set(DeviceState.CONNECTING, self.url)
        last: Exception | None = None
        for i in range(self.reconnect_retries):
            try:
                self._ws = await websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=16 * 1024 * 1024,
                )
                await self._ws.send(
                    device_hello(
                        self.device_id,
                        self.device_type,
                        token=self.token,
                        tts_id=self.tts_id,
                    )
                )
                resp = json.loads(await self._ws.recv())
                if resp.get("type") == "error":
                    raise RuntimeError(resp.get("payload", {}).get("detail", "auth error"))
                if resp.get("type") != "session.accept":
                    raise RuntimeError(f"unexpected: {resp}")
                self.session_id = resp["payload"]["session_id"]
                self._set(DeviceState.ONLINE, self.session_id or "")
                logger.info("Connected session={}", self.session_id)
                self._hb = asyncio.create_task(self._heartbeat())
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                delay = self.reconnect_delay * (2 ** min(i, 5))
                self._set(DeviceState.CONNECTING, f"retry {i + 1}")
                logger.warning("connect failed: {} — wait {:.1f}s", exc, delay)
                await asyncio.sleep(delay)
        self._set(DeviceState.ERROR, "connect failed")
        raise RuntimeError(f"cannot connect: {last}")

    async def close(self) -> None:
        if self._hb:
            self._hb.cancel()
        if self._ws:
            await self._ws.close()

    async def _heartbeat(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.heartbeat_seconds)
                if self._ws:
                    await self._ws.send(ping())
        except (asyncio.CancelledError, ConnectionClosed):
            return

    async def talk_once(self, stop_event) -> None:
        """Record until stop_event (second click / Enter), then send + recv."""
        assert self._ws and self.session_id
        self._set(DeviceState.LISTENING, "再点结束")
        audio = await asyncio.to_thread(
            record_until_stop,
            stop_event,
            self.sample_rate,
            max_seconds=max(self.record_seconds, 60.0),
        )
        await self._ws.send(audio_start(self.session_id))
        chunk = 4096
        for i in range(0, len(audio), chunk):
            await self._ws.send(audio[i : i + chunk])
        await self._ws.send(audio_end(self.session_id))
        self._set(DeviceState.PROCESSING)
        await self._recv_turn()

    async def cancel(self) -> None:
        if self._ws and self.session_id:
            await self._ws.send(session_cancel(self.session_id))

    async def _recv_turn(self) -> None:
        assert self._ws
        tts_buf = bytearray()
        fmt = "wav"
        seg_n = 0
        end = {"agent.done", "agent.cancel", "agent.error", "error"}
        self._view.reset_turn()

        while True:
            raw = await self._ws.recv()
            if isinstance(raw, bytes):
                tts_buf.extend(raw)
                continue
            msg = json.loads(raw)
            mtype = msg["type"]
            payload = msg.get("payload", {})
            if mtype == "device.pong":
                continue

            oled = self._view.handle(mtype, payload)
            if mtype == "stt.final":
                self._set(DeviceState.PROCESSING, oled or self._view.last_oled_line)
            elif mtype == "agent.thinking":
                self._set(DeviceState.PROCESSING, "思考中")
            elif mtype == "agent.tool_call":
                self._set(DeviceState.PROCESSING, oled or "工具")
            elif mtype == "agent.message":
                self._set(DeviceState.PROCESSING, oled or self._view.last_oled_line)
            elif mtype == "tts.start":
                fmt = payload.get("format") or "wav"
                tts_buf.clear()
                self._set(DeviceState.SPEAKING, "播放中")
            elif mtype == "tts.end":
                if tts_buf:
                    seg_n += 1
                    ext = sniff_ext(bytes(tts_buf), fmt)
                    name = "response." + ext if seg_n == 1 else f"response-{seg_n}.{ext}"
                    out = Path(name)
                    out.write_bytes(tts_buf)
                    await asyncio.to_thread(play_file, out)
                    tts_buf.clear()
            elif mtype in end:
                break

        self._set(DeviceState.ONLINE)
