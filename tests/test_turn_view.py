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
    assert any(x.startswith("助手：") for x in lines)
    assert any(x.startswith("思考：") for x in lines)


def test_stt_and_tools() -> None:
    lines: list[str] = []
    view = TurnView(print=lines.append, thinking_min_interval=0)
    view.handle("stt.final", {"text": "开灯"})
    view.handle("agent.tool_call", {"tool": "home.light"})
    view.handle("agent.tool_result", {"tool": "home.light", "status": "success"})
    assert lines[0].startswith("你：")
    assert "工具：home.light" in lines[1]
    assert "结果：" in lines[2]
