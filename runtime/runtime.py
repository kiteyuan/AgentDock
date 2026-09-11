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
from runtime.pets import pets_root as resolve_pets_root
from runtime.pets.http_server import build_assets_base_url, start_pets_http_server
from runtime.security.auth import DeviceAuth
from runtime.security.permissions import PermissionGuard
from runtime.session.manager import SessionManager
from runtime.transport.speech.base import STTProvider
from runtime.transport.speech.factory import create_tts
from runtime.transport.speech.registry import TTSRegistry
from runtime.workspace import resolve_workspace


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
        self.workspace = resolve_workspace(cfg, ensure=True)
        self.pipeline = BridgePipeline(
            self.router,
            tts_registry=self.tts_registry,
            workspace=str(self.workspace),
        )
        server = cfg.get("server", {})
        network = cfg.get("network", {})
        self.pets_root = resolve_pets_root(cfg)
        self.assets_port = int(server.get("assets_port", 8766))
        self.assets_base_url = build_assets_base_url(
            host_hint=server.get("host", "0.0.0.0"),
            port=self.assets_port,
            advertise_url=network.get("advertise_url"),
            assets_url=network.get("assets_url"),
        )
        self._pets_httpd = None
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
            pets_root=self.pets_root,
            assets_port=self.assets_port,
            assets_base_url=self.assets_base_url,
        )

    async def start(self) -> None:
        if self.stt is not None and hasattr(self.stt, "warm"):
            try:
                await asyncio.to_thread(self.stt.warm)
            except Exception:
                logger.exception("STT warm-up failed; will load on first audio")
        try:
            self._pets_httpd = start_pets_http_server(
                host=self.cfg.get("server", {}).get("host", "0.0.0.0"),
                port=self.assets_port,
                pets_root=self.pets_root,
            )
        except OSError:
            logger.exception(
                "Pet assets HTTP failed to bind :{} — clients will not download pets",
                self.assets_port,
            )
        logger.info(
            "AgentDock Runtime ready | agents={} | tts={} | default_agent={} | default_tts={} | workspace={} | pets={}",
            self.registry.ids(),
            self.tts_registry.ids(),
            self.router.default_agent_id,
            self.tts_registry.default_id,
            self.workspace,
            self.pets_root,
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
