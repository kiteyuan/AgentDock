"""Runtime facade — wires Session, Registry, Router, TTS, Pipeline, Gateway."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from runtime.agent.factory import create_agent
from runtime.agent.registry import AgentRegistry
from runtime.agent.router import AgentRouter
from runtime.bridge.pipeline import BridgePipeline
from runtime.device.gateway import DeviceGateway
from runtime.security.auth import DeviceAuth
from runtime.security.permissions import PermissionGuard
from runtime.session.manager import SessionManager
from runtime.transport.speech.base import STTProvider
from runtime.transport.speech.factory import create_tts
from runtime.transport.speech.registry import TTSRegistry


class Runtime:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.sessions = SessionManager()
        self.registry = AgentRegistry()
        self.tts_registry = TTSRegistry()
        self.permissions = PermissionGuard()
        self.auth = self._build_auth(cfg.get("security", {}))
        self._register_agents(cfg.get("agent", {}))
        self._register_tts(cfg.get("tts", {}))
        default_id = cfg.get("agent", {}).get("default", "mock")
        self.router = AgentRouter(
            self.registry, default_agent_id=default_id, permissions=self.permissions
        )
        self.stt = self._build_stt(cfg.get("stt", {}))
        self.pipeline = BridgePipeline(self.router, tts_registry=self.tts_registry)
        server = cfg.get("server", {})
        network = cfg.get("network", {})
        tls = server.get("tls") or {}
        ssl_cert = ssl_key = None
        if bool(tls.get("enabled")):
            from pathlib import Path

            root = Path(__file__).resolve().parents[1]
            cert = tls.get("cert") or "certs/cert.pem"
            key = tls.get("key") or "certs/key.pem"
            ssl_cert = Path(cert) if Path(cert).is_absolute() else root / cert
            ssl_key = Path(key) if Path(key).is_absolute() else root / key
            if not ssl_cert.is_file() or not ssl_key.is_file():
                # Auto-generate local CA + server cert for LAN HTTPS/WSS
                import sys

                sys.path.insert(0, str(root))
                from certs.ensure import ensure_certs

                _, ssl_cert, ssl_key = ensure_certs(root / "certs")
        self.gateway = DeviceGateway(
            host=server.get("host", "0.0.0.0"),
            port=server.get("port", 8765),
            sessions=self.sessions,
            auth=self.auth,
            pipeline=self.pipeline,
            registry=self.registry,
            tts_registry=self.tts_registry,
            stt=self.stt,
            advertise_url=network.get("advertise_url"),
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
        )

    async def start(self) -> None:
        if self.stt is not None and hasattr(self.stt, "warm"):
            try:
                await asyncio.to_thread(self.stt.warm)
            except Exception:
                logger.exception("STT warm-up failed; will load on first audio")
        logger.info(
            "AgentDock Runtime ready | agents={} | tts={} | default_agent={} | default_tts={}",
            self.registry.ids(),
            self.tts_registry.ids(),
            self.router.default_agent_id,
            self.tts_registry.default_id,
        )
        await self.gateway.start()

    def _build_auth(self, sec: dict[str, Any]) -> DeviceAuth:
        return DeviceAuth(
            require_token=bool(sec.get("require_token", False)),
            tokens=list(sec.get("tokens") or []),
        )

    def _register_agents(self, agent_cfg: dict[str, Any]) -> None:
        agents = agent_cfg.get("agents") or {
            "mock": {"type": "mock"},
            "echo": {"type": "echo"},
        }
        for aid, acfg in agents.items():
            self.registry.register(create_agent(aid, acfg or {}))

        default_id = agent_cfg.get("default", "mock")
        if self.registry.get(default_id) is None:
            from runtime.agent.adapters.mock import MockAgent

            self.registry.register(MockAgent())

    def _register_tts(self, tts_cfg: dict[str, Any]) -> None:
        provider = tts_cfg.get("provider", "none")
        providers = tts_cfg.get("providers")

        # Legacy single-provider form: tts.provider: echo
        if not providers:
            if provider in (None, "none", "off", ""):
                return
            providers = {provider: {"type": provider, **(tts_cfg.get(provider) or {})}}

        default = tts_cfg.get("default", provider)
        enable_default = default not in (None, "none", "off", "")

        for tid, tcfg in providers.items():
            ptype = (tcfg or {}).get("type", tid)
            if ptype in (None, "none", "off"):
                continue
            p = create_tts(tid, tcfg or {})
            self.tts_registry.register(p, default=(enable_default and tid == default))

    def _build_stt(self, cfg: dict[str, Any]) -> STTProvider | None:
        provider = cfg.get("provider", "whisper")
        if provider in (None, "none", "off", ""):
            return None
        if provider == "whisper":
            from runtime.transport.speech.whisper_stt import WhisperSTT

            opts = cfg.get("whisper", {})
            kwargs = {
                "model": opts.get("model", "small"),
                "device": opts.get("device", "cpu"),
                "language": opts.get("language", "auto"),
                "beam_size": int(opts.get("beam_size", 5)),
                "vad_filter": bool(opts.get("vad_filter", True)),
            }
            if "initial_prompt" in opts:
                kwargs["initial_prompt"] = opts.get("initial_prompt") or None
            if "code_switch" in opts:
                kwargs["code_switch"] = bool(opts.get("code_switch"))
            return WhisperSTT(**kwargs)
        raise ValueError(f"unknown STT provider: {provider}")
