"""Silent / stub TTS for pipeline testing."""

from __future__ import annotations

import struct

from runtime.transport.speech.base import TTSInfo, TTSProvider


class EchoTTS(TTSProvider):
    def __init__(self, tts_id: str = "echo", name: str = "Echo TTS") -> None:
        self._id = tts_id
        self._name = name

    @property
    def info(self) -> TTSInfo:
        return TTSInfo(
            id=self._id,
            name=self._name,
            provider="echo",
            description="Silent WAV stub (no real speech).",
            models=["silent"],
        )

    async def synthesize(self, text: str, *, model: str | None = None) -> bytes:
        sample_rate = 16000
        bits = 16
        channels = 1
        data_size = 0
        return struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            channels,
            sample_rate,
            sample_rate * channels * bits // 8,
            channels * bits // 8,
            bits,
            b"data",
            data_size,
        )
