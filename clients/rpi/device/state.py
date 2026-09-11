"""Device UI states for OLED / console."""

from __future__ import annotations

from enum import Enum


class DeviceState(str, Enum):
    BOOT = "BOOT"
    CONNECTING = "CONNECTING"
    ONLINE = "ONLINE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
