"""Build TTS providers from config."""

from __future__ import annotations

import importlib
from typing import Any

from runtime.transport.speech.base import TTSProvider


def create_tts(tts_id: str, cfg: dict[str, Any]) -> TTSProvider:
    ptype = cfg.get("type", tts_id)

    if ptype == "echo":
        from runtime.transport.speech.echo_tts import EchoTTS

        return EchoTTS(tts_id=tts_id, name=cfg.get("name", "Echo TTS"))
    if ptype == "edge":
        from runtime.transport.speech.edge_tts import EdgeTTS

        return EdgeTTS(
            tts_id=tts_id,
            name=cfg.get("name", "Edge TTS"),
            voice=cfg.get("voice") or cfg.get("model") or "zh-CN-XiaoxiaoNeural",
            voices=list(cfg.get("models") or cfg.get("voices") or []) or None,
        )
    if ptype in ("gpt-sovits", "voice", "haibara"):
        from runtime.transport.speech.gpt_sovits_tts import GPTSoVITSTTS

        return GPTSoVITSTTS(
            tts_id=tts_id,
            name=cfg.get("name"),
            voice_dir=cfg.get("voice_dir") or cfg.get("voices_dir") or f"voices/{tts_id}",
            url=cfg.get("url") or "http://127.0.0.1:9880",
            api=cfg.get("api") or "v2",
            text_lang=cfg.get("text_lang") or "auto",
            timeout=float(cfg.get("timeout", 120)),
            load_weights=bool(cfg.get("load_weights", True)),
        )
    if ptype == "http":
        from runtime.transport.speech.http_tts import HTTPTTS

        return HTTPTTS(
            url=cfg["url"],
            tts_id=tts_id,
            name=cfg.get("name", "HTTP TTS"),
            model=cfg.get("model"),
            models=list(cfg.get("models") or []),
            headers=dict(cfg.get("headers") or {}),
            timeout=float(cfg.get("timeout", 60)),
        )
    if ptype == "import" or ":" in str(ptype):
        path = cfg.get("path") or ptype
        return _load_import(path, cfg, tts_id)
    raise ValueError(f"unknown TTS type: {ptype}")


def _load_import(path: str, cfg: dict[str, Any], tts_id: str) -> TTSProvider:
    if ":" not in path:
        raise ValueError(f"import path must be 'module:Class', got {path!r}")
    mod_name, cls_name = path.rsplit(":", 1)
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    kwargs = {k: v for k, v in cfg.items() if k not in ("type", "path")}
    kwargs.setdefault("tts_id", tts_id)
    obj = cls(**kwargs)
    if not isinstance(obj, TTSProvider):
        raise TypeError(f"{path} did not return TTSProvider")
    return obj
