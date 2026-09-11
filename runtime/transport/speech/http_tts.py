"""HTTP TTS — call any HTTP endpoint that returns audio bytes or JSON{audio_base64}."""

from __future__ import annotations

import asyncio
import base64
import json
import urllib.request

from runtime.transport.speech.base import TTSInfo, TTSProvider


class HTTPTTS(TTSProvider):
    def __init__(
        self,
        url: str,
        tts_id: str = "http-tts",
        *,
        name: str = "HTTP TTS",
        model: str | None = None,
        models: list[str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 60,
    ) -> None:
        self.url = url
        self._id = tts_id
        self._name = name
        self.default_model = model
        self._models = models or ([model] if model else [])
        self.headers = headers or {}
        self.timeout = timeout

    @property
    def info(self) -> TTSInfo:
        return TTSInfo(
            id=self._id,
            name=self._name,
            provider="http",
            description=f"HTTP TTS → {self.url}",
            models=list(self._models),
        )

    async def synthesize(self, text: str, *, model: str | None = None) -> bytes:
        return await asyncio.to_thread(self._call, text, model or self.default_model)

    def _call(self, text: str, model: str | None) -> bytes:
        body = json.dumps({"text": text, "model": model}).encode()
        headers = {"Content-Type": "application/json", **self.headers}
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
        if "application/json" in content_type:
            obj = json.loads(data)
            b64 = obj.get("audio_base64") or obj.get("audio") or obj.get("data")
            if not b64:
                raise ValueError("HTTP TTS JSON response missing audio_base64")
            return base64.b64decode(b64)
        return data
