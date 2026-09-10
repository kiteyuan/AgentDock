"""Device Gateway — WebSocket entry for Device Protocol."""

from __future__ import annotations

import asyncio
from pathlib import Path

import websockets
from loguru import logger

from runtime.agent.registry import AgentRegistry
from runtime.bridge.bus import EventBus
from runtime.bridge.pipeline import BridgePipeline
from runtime.device.connection import DeviceConnection
from runtime.protocol.device import (
    DeviceMessageType,
    agents_list_result,
    error_msg,
    pong,
    session_accept,
    stt_final,
    tts_list_result,
    tts_selected,
)
from runtime.protocol.wire import decode_message, encode_message
from runtime.security.auth import DeviceAuth
from runtime.session.manager import SessionManager
from runtime.transport.speech.base import STTProvider
from runtime.transport.speech.registry import TTSRegistry


class DeviceGateway:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        sessions: SessionManager,
        auth: DeviceAuth,
        pipeline: BridgePipeline,
        registry: AgentRegistry,
        tts_registry: TTSRegistry,
        stt: STTProvider | None = None,
        advertise_url: str | None = None,
        ssl_cert: str | Path | None = None,
        ssl_key: str | Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.sessions = sessions
        self.auth = auth
        self.pipeline = pipeline
        self.registry = registry
        self.tts_registry = tts_registry
        self.stt = stt
        self.advertise_url = advertise_url
        self.ssl_cert = Path(ssl_cert) if ssl_cert else None
        self.ssl_key = Path(ssl_key) if ssl_key else None

    async def start(self) -> None:
        ssl_ctx = None
        scheme = "ws"
        if self.ssl_cert and self.ssl_key:
            import ssl

            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(certfile=str(self.ssl_cert), keyfile=str(self.ssl_key))
            scheme = "wss"
        logger.info("DeviceGateway on {}://{}:{}", scheme, self.host, self.port)
        if self.advertise_url:
            logger.info("Advertise URL (Tailscale/public): {}", self.advertise_url)
        async with websockets.serve(
            self._handler,
            self.host,
            self.port,
            max_size=16 * 1024 * 1024,
            ssl=ssl_ctx,
        ):
            await asyncio.Future()

    async def _handler(self, ws: websockets.WebSocketServerProtocol) -> None:
        conn = DeviceConnection(ws=ws)
        turn_task: asyncio.Task | None = None
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    conn.audio_buf.extend(raw)
                    continue
                turn_task = await self._dispatch(conn, raw, turn_task)
        except websockets.ConnectionClosed:
            logger.info("Device disconnected: {}", conn.device_id)
        finally:
            if turn_task and not turn_task.done():
                turn_task.cancel()
            if conn.session:
                conn.session.request_cancel()
                self.sessions.remove(conn.session.session_id)

    async def _dispatch(
        self,
        conn: DeviceConnection,
        raw: str,
        turn_task: asyncio.Task | None,
    ) -> asyncio.Task | None:
        try:
            msg = decode_message(raw)
        except Exception as exc:  # noqa: BLE001
            await conn.send(encode_message(error_msg(f"bad message: {exc}")))
            return turn_task

        if msg.type == DeviceMessageType.DEVICE_HELLO:
            device_id = msg.payload.get("device_id", "unknown")
            token = msg.payload.get("token")
            result = self.auth.authenticate(device_id, token)
            if not result.ok:
                await conn.send(encode_message(error_msg(result.reason or "auth failed")))
                await conn.ws.close()
                return turn_task
            conn.device_id = device_id
            conn.device_type = msg.payload.get("device_type", "unknown")
            conn.session = self.sessions.create(device_id, conn.device_type)
            preferred_tts = msg.payload.get("tts_id") or self.tts_registry.default_id
            if preferred_tts and self.tts_registry.get(preferred_tts):
                conn.session.tts_id = preferred_tts
            await conn.send(
                encode_message(
                    session_accept(
                        conn.session.session_id,
                        device_id,
                        advertise_url=self.advertise_url,
                        tts_id=conn.session.tts_id,
                    )
                )
            )
            logger.info("Device connected: {} ({})", device_id, conn.device_type)
            return turn_task

        if msg.type == DeviceMessageType.PING:
            await conn.send(encode_message(pong(msg.payload.get("ping_id") or msg.id)))
            return turn_task

        if msg.type == DeviceMessageType.AGENTS_LIST:
            await conn.send(encode_message(agents_list_result(self.registry.list_dicts())))
            return turn_task

        if msg.type == DeviceMessageType.TTS_LIST:
            await conn.send(
                encode_message(
                    tts_list_result(self.tts_registry.list_dicts(), self.tts_registry.default_id)
                )
            )
            return turn_task

        if msg.type == DeviceMessageType.TTS_SELECT:
            sid = msg.payload.get("session_id", "")
            tts_id = msg.payload.get("tts_id", "")
            model = msg.payload.get("model")
            session = self.sessions.get(sid)
            if not session:
                await conn.send(encode_message(error_msg("unknown session")))
                return turn_task
            if tts_id and not self.tts_registry.get(tts_id):
                await conn.send(encode_message(error_msg(f"unknown tts: {tts_id}", sid)))
                return turn_task
            session.tts_id = tts_id or None
            session.tts_model = model
            await conn.send(encode_message(tts_selected(sid, tts_id, model)))
            return turn_task

        if msg.type == DeviceMessageType.SESSION_CANCEL:
            sid = msg.payload.get("session_id", "")
            session = self.sessions.get(sid)
            if session:
                session.request_cancel()
                logger.info("[{}] cancel requested", sid)
            return turn_task

        if msg.type == DeviceMessageType.USER_MESSAGE:
            sid = msg.payload.get("session_id", "")
            text = msg.payload.get("text", "")
            agent_id = msg.payload.get("agent_id")
            tts_id = msg.payload.get("tts_id")
            tts_model = msg.payload.get("tts_model")
            session = self.sessions.get(sid)
            if not session:
                await conn.send(encode_message(error_msg("unknown session")))
                return turn_task
            bus = EventBus(conn.send)
            task = asyncio.create_task(
                self.pipeline.run_turn(
                    session,
                    text,
                    bus,
                    agent_id=agent_id,
                    tts_id=tts_id,
                    tts_model=tts_model,
                )
            )
            return task

        if msg.type == DeviceMessageType.AUDIO_START:
            conn.audio_buf.clear()
            return turn_task

        if msg.type == DeviceMessageType.AUDIO_END:
            sid = msg.payload.get("session_id", "")
            session = self.sessions.get(sid)
            if not session:
                await conn.send(encode_message(error_msg("unknown session")))
                return turn_task
            if not self.stt:
                await conn.send(
                    encode_message(error_msg("STT not configured; use user.message", sid))
                )
                return turn_task
            audio = bytes(conn.audio_buf)
            conn.audio_buf.clear()
            try:
                text = await self.stt.transcribe(audio)
            except Exception as exc:
                logger.exception("STT failed")
                await conn.send(encode_message(error_msg(f"STT failed: {exc}", sid)))
                return turn_task
            if not text.strip():
                await conn.send(encode_message(error_msg("STT produced empty text", sid)))
                return turn_task
            await conn.send(encode_message(stt_final(sid, text)))
            bus = EventBus(conn.send)
            task = asyncio.create_task(self.pipeline.run_turn(session, text, bus))
            return task

        return turn_task
