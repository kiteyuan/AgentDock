"""Human-readable turn rendering for Device clients (collapse thinking spam)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


PrintFn = Callable[[str], None]


@dataclass
class TurnView:
    """
    Fold agent/stt/tts wire events into short console / OLED lines.

    thinking tokens are merged and throttled (not one print per token).
    """

    print: PrintFn = field(default=lambda s: print(s, flush=True))
    thinking_min_interval: float = 0.4
    thinking_max_len: int = 56
    oled_width: int = 21

    _thinking_buf: str = field(default="", init=False, repr=False)
    _last_thinking_flush: float = field(default=0.0, init=False, repr=False)
    _thinking_printed: bool = field(default=False, init=False, repr=False)
    last_oled_line: str = field(default="", init=False)
    last_user_text: str | None = field(default=None, init=False)
    last_assistant_text: str | None = field(default=None, init=False)

    def reset_turn(self) -> None:
        self._emit_thinking(final=True)
        self._thinking_buf = ""
        self._thinking_printed = False
        self.last_user_text = None
        self.last_assistant_text = None

    def handle(self, mtype: str, payload: dict[str, Any] | None = None) -> str | None:
        """Process one event; return a short OLED-friendly line if UI should update."""
        payload = payload or {}
        if mtype == "device.pong":
            return None

        if mtype == "stt.final":
            self._emit_thinking(final=True)
            text = (payload.get("text") or "").strip()
            self.last_user_text = text
            line = f"你：{text}" if text else "你：（空）"
            self.print(line)
            self.last_oled_line = self._oled(text or "…")
            return self.last_oled_line

        if mtype == "agent.thinking":
            chunk = payload.get("content") or payload.get("text") or ""
            if not chunk:
                return None
            self._thinking_buf += str(chunk)
            now = time.monotonic()
            if self._last_thinking_flush <= 0:
                self._last_thinking_flush = now
            elif (now - self._last_thinking_flush) >= self.thinking_min_interval:
                self._emit_thinking(final=False)
            self.last_oled_line = "思考中"
            return self.last_oled_line

        if mtype == "agent.tool_call":
            self._emit_thinking(final=True)
            tool = payload.get("tool") or "tool"
            self.print(f"工具：{tool}")
            self.last_oled_line = self._oled(f"工具:{tool}")
            return self.last_oled_line

        if mtype == "agent.tool_result":
            self._emit_thinking(final=True)
            tool = payload.get("tool") or "tool"
            status = payload.get("status") or "ok"
            self.print(f"结果：{tool} · {status}")
            self.last_oled_line = self._oled(f"结果:{status}")
            return self.last_oled_line

        if mtype == "agent.message":
            self._emit_thinking(final=True)
            text = (payload.get("content") or payload.get("text") or "").strip()
            self.last_assistant_text = text
            self.print(f"助手：{text}" if text else "助手：（空）")
            self.last_oled_line = self._oled(text or "…")
            return self.last_oled_line

        if mtype == "agent.start":
            self._emit_thinking(final=True)
            self.print("… Agent 开始")
            self.last_oled_line = "处理中"
            return self.last_oled_line

        if mtype == "tts.start":
            self._emit_thinking(final=True)
            tid = payload.get("tts_id") or ""
            self.print(f"播放中… ({tid})" if tid else "播放中…")
            self.last_oled_line = "播放中"
            return self.last_oled_line

        if mtype == "tts.end":
            self.print("播放结束")
            self.last_oled_line = "在线"
            return self.last_oled_line

        if mtype in ("agent.error", "error"):
            self._emit_thinking(final=True)
            detail = payload.get("content") or payload.get("detail") or payload.get("text") or "error"
            self.print(f"错误：{detail}")
            self.last_oled_line = self._oled(f"错误:{detail}")
            return self.last_oled_line

        if mtype == "agent.cancel":
            self._emit_thinking(final=True)
            self.print("已取消")
            self.last_oled_line = "已取消"
            return self.last_oled_line

        if mtype == "agent.done":
            self._emit_thinking(final=True)
            return None

        return None

    def _emit_thinking(self, *, final: bool) -> None:
        shown = self._thinking_buf.strip()
        if not shown:
            if final:
                self._thinking_buf = ""
                self._thinking_printed = False
            return
        if len(shown) > self.thinking_max_len:
            shown = "…" + shown[-(self.thinking_max_len - 1) :]
        # Only print when we have new content; final emits once more if never printed
        if not final and shown:
            self.print(f"思考：{shown}")
            self._thinking_printed = True
            self._last_thinking_flush = time.monotonic()
        elif final and shown and not self._thinking_printed:
            self.print(f"思考：{shown}")
            self._thinking_printed = True
        if final:
            self._thinking_buf = ""
            self._thinking_printed = False
            self._last_thinking_flush = time.monotonic()

    def _oled(self, text: str) -> str:
        text = (text or "").replace("\n", " ").strip()
        if len(text) <= self.oled_width:
            return text
        return text[: self.oled_width - 1] + "…"
