"""TurnView collapses thinking spam into throttled lines."""

from __future__ import annotations

from turn_view import TurnView


def test_thinking_throttled() -> None:
    lines: list[str] = []
    view = TurnView(print=lines.append, thinking_min_interval=10.0)
    view.handle("agent.thinking", {"content": "Hel"})
    view.handle("agent.thinking", {"content": "lo"})
    # Within interval: no print yet
    assert lines == []
    view.handle("agent.message", {"content": "你好"})
    assert "你好" in lines
    assert any("Hello" in x for x in lines)


def test_stt_and_tools() -> None:
    lines: list[str] = []
    view = TurnView(print=lines.append, thinking_min_interval=0)
    view.handle("stt.final", {"text": "开灯"})
    view.handle("agent.tool_call", {"tool": "home.light"})
    view.handle("agent.tool_result", {"tool": "home.light", "status": "success", "content": "ok"})
    assert "开灯" not in lines  # STT is not a process line
    assert lines[0] == "home.light"
    assert lines[1] == "ok"
