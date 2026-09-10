"""Bridge pipeline — one turn: intent → route → agent.run → events → device (+ optional TTS)."""

from __future__ import annotations

import asyncio

from loguru import logger

from runtime.agent.router import AgentRouter
from runtime.bridge.bus import EventBus
from runtime.protocol.agent import AgentEventType, AgentRequest, agent_error
from runtime.protocol.device import tts_end, tts_start
from runtime.protocol.wire import encode_message
from runtime.session.models import Session
from runtime.transport.speech.registry import TTSRegistry
from runtime.transport.speech.speak_text import SentenceBuffer, is_speakable, speak_text


class BridgePipeline:
    def __init__(
        self,
        router: AgentRouter,
        tts_registry: TTSRegistry | None = None,
    ) -> None:
        self.router = router
        self.tts_registry = tts_registry or TTSRegistry()

    async def _synthesize_segment(
        self,
        session: Session,
        bus: EventBus,
        text: str,
    ) -> None:
        tts = self.tts_registry.get(session.tts_id)
        if not tts or not is_speakable(text):
            if text and not is_speakable(text):
                logger.info("[{}] skip non-speakable TTS chunk {!r}", session.session_id, text)
            return

        audio: bytes | None = None
        used = tts
        try:
            audio = await tts.synthesize(text, model=session.tts_model)
        except Exception as exc:
            # Invalid / empty text: do not switch voice to Edge mid-turn
            msg = str(exc)
            if "有效文本" in msg or "invalid" in msg.lower():
                logger.warning("[{}] skip invalid TTS text {!r}: {}", session.session_id, text, exc)
                return
            logger.exception("TTS failed")
            fallback = self.tts_registry.get("edge")
            if fallback and fallback.info.id != tts.info.id:
                try:
                    logger.warning("falling back to edge TTS: {}", exc)
                    used = fallback
                    audio = await fallback.synthesize(text, model=session.tts_model)
                except Exception as exc2:
                    logger.exception("fallback TTS failed")
                    await bus.publish(agent_error(session.session_id, f"TTS failed: {exc2}"))
                    return
            else:
                await bus.publish(agent_error(session.session_id, f"TTS failed: {exc}"))
                return

        if not audio:
            await bus.publish(agent_error(session.session_id, "TTS returned empty audio"))
            return

        fmt = "mp3" if used.info.provider == "edge" else "wav"
        if used.info.provider == "http":
            fmt = "audio"
        await bus._send(
            encode_message(
                tts_start(session.session_id, used.info.id, format=fmt, text=text)
            )
        )
        await bus._send(audio)
        await bus._send(encode_message(tts_end(session.session_id)))

    async def run_turn(
        self,
        session: Session,
        text: str,
        bus: EventBus,
        *,
        agent_id: str | None = None,
        tts_id: str | None = None,
        tts_model: str | None = None,
    ) -> None:
        session.reset_cancel()
        session.add_turn("user", text)

        if tts_id:
            session.tts_id = tts_id
        if tts_model:
            session.tts_model = tts_model

        try:
            adapter = self.router.resolve(device_id=session.device_id, agent_id=agent_id)
        except (KeyError, PermissionError) as exc:
            await bus.publish(agent_error(session.session_id, str(exc)))
            return

        session.agent_id = adapter.info.id
        request = AgentRequest(
            session_id=session.session_id,
            text=text,
            context=list(session.context),
            device=session.device_info(),
            agent_id=adapter.info.id,
            cancel_event=session.cancel_event,
        )

        speak_buf = SentenceBuffer()
        speak_q: asyncio.Queue[str | None] = asyncio.Queue()
        tts = self.tts_registry.get(session.tts_id)

        async def tts_worker() -> None:
            while True:
                item = await speak_q.get()
                if item is None:
                    break
                await self._synthesize_segment(session, bus, item)

        worker: asyncio.Task[None] | None = None
        if tts:
            worker = asyncio.create_task(tts_worker())

        async def enqueue_sentences(parts: list[str]) -> None:
            if not worker:
                return
            for sent in parts:
                if not is_speakable(sent):
                    continue
                logger.info("[{}] TTS sentence ({} chars) {!r}", session.session_id, len(sent), sent[:40])
                await speak_q.put(sent)

        terminal = None
        async for event in adapter.run(request):
            logger.info("[{}] {}", session.session_id, event.type.value)

            if event.type in (
                AgentEventType.DONE,
                AgentEventType.CANCEL,
                AgentEventType.ERROR,
            ):
                # Defer terminal event until after TTS so clients don't hang up early
                terminal = event
                break

            await bus.publish(event)

            if event.type == AgentEventType.MESSAGE and event.content:
                session.add_turn("assistant", event.content)
                # Dual-channel: only speak=True messages go to TTS
                if event.speak and worker:
                    piece = speak_text(event.content)
                    if piece and piece != event.content.strip():
                        logger.info("[{}] speak_text sanitized for TTS", session.session_id)
                    if piece:
                        await enqueue_sentences(speak_buf.push(piece))

        # Only flush remainder on a successful done turn
        if worker:
            if terminal is None or terminal.type == AgentEventType.DONE:
                await enqueue_sentences(speak_buf.flush())
            await speak_q.put(None)
            await worker

        if terminal is not None:
            await bus.publish(terminal)
