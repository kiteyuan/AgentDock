"""Device authentication skeleton."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthResult:
    ok: bool
    device_id: str
    reason: str | None = None


class DeviceAuth:
    """Token gate. When require_token is False, all devices pass."""

    def __init__(self, *, require_token: bool = False, tokens: list[str] | None = None) -> None:
        self.require_token = require_token
        self.tokens = set(tokens or [])

    def authenticate(self, device_id: str, token: str | None = None) -> AuthResult:
        if not self.require_token:
            return AuthResult(ok=True, device_id=device_id)
        if token and token in self.tokens:
            return AuthResult(ok=True, device_id=device_id)
        return AuthResult(ok=False, device_id=device_id, reason="invalid or missing device token")
