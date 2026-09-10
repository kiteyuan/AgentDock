"""Mock Agent — full multi-step event stream for bridge tests."""

from __future__ import annotations

import asyncio

from runtime.agent.base import AgentAdapter
from runtime.protocol.agent import (
    AgentEventStream,
    AgentInfo,
    AgentRequest,
    agent_cancel,
    agent_done,
    agent_message,
    agent_start,
    agent_thinking,
    agent_tool_call,
    agent_tool_result,
)


class MockAgent(AgentAdapter):
    @property
    def info(self) -> AgentInfo:
        return AgentInfo(
            id="mock",
            name="Mock Agent",
            capabilities=["demo", "filesystem"],
            description="Emits thinking / tool_call / tool_result / message for bridge tests.",
        )

    async def run(self, request: AgentRequest) -> AgentEventStream:
        sid = request.session_id
        cancel = request.cancel_event

        yield agent_start(sid)
        if cancel and cancel.is_set():
            yield agent_cancel(sid, "cancelled before thinking")
            return

        await asyncio.sleep(0.05)
        yield agent_thinking(sid, f"收到请求：「{request.text}」，开始规划步骤")

        if cancel and cancel.is_set():
            yield agent_cancel(sid)
            return

        await asyncio.sleep(0.08)
        if cancel and cancel.is_set():
            yield agent_cancel(sid, "cancelled before tool call")
            return

        yield agent_tool_call(sid, "filesystem.list", {"path": "~/Desktop"})
        await asyncio.sleep(0.05)

        if cancel and cancel.is_set():
            yield agent_cancel(sid, "cancelled during tool call")
            return

        yield agent_tool_result(
            sid,
            "filesystem.list",
            status="success",
            content="listed 3 items",
            data={"items": ["a.txt", "b.pdf", "notes"]},
        )

        await asyncio.sleep(0.05)
        if cancel and cancel.is_set():
            yield agent_cancel(sid)
            return

        yield agent_tool_call(sid, "filesystem.organize", {"path": "~/Desktop"})
        await asyncio.sleep(0.05)
        yield agent_tool_result(sid, "filesystem.organize", status="success", content="organized")

        yield agent_message(sid, f"已经处理完：「{request.text}」")
        yield agent_done(sid)
