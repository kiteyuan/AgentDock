"""Session Manager."""

from __future__ import annotations

import uuid

from loguru import logger

from runtime.session.models import Session


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._by_device: dict[str, str] = {}

    def create(self, device_id: str, device_type: str = "unknown") -> Session:
        sid = uuid.uuid4().hex[:12]
        session = Session(session_id=sid, device_id=device_id, device_type=device_type)
        self._sessions[sid] = session
        self._by_device[device_id] = sid
        logger.info("Session created: {} for device {}", sid, device_id)
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def get_by_device(self, device_id: str) -> Session | None:
        sid = self._by_device.get(device_id)
        return self._sessions.get(sid) if sid else None

    def remove(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session and self._by_device.get(session.device_id) == session_id:
            self._by_device.pop(session.device_id, None)

    @property
    def active_count(self) -> int:
        return len(self._sessions)
