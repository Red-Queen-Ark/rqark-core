import asyncio
import json
from dataclasses import replace
from typing import Any

from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta

from rqark_core.libs.event import EventFunction
from rqark_core.types.chat import AssistantMessage, Chunk, Message, ToolCall, ToolMessage, Usage
from rqark_core.types.tool import BaseTool, ToolContext


class ChunkHandler:
    def __init__(self, _emit_chunk: EventFunction[Chunk]) -> None:
        self.content = ""
        self.reasoning = ""
        self.usage: Usage | None = None
        self.tc_acc: dict[int, dict[str, Any]] = {}
        self._emit_chunk = _emit_chunk

    async def message(self) -> AssistantMessage:
        tool_calls: list[ToolCall] | None = None
        if self.tc_acc:
            tool_calls = [self._to_tool_call(self.tc_acc[i]) for i in sorted(self.tc_acc)]
            await self._emit_chunk(Chunk('tool_calls', tool_calls))
        if self.usage:
            await self._emit_chunk(Chunk('usage', self.usage))
        assistant_message = AssistantMessage(
            content=self.content,
            tool_calls=tool_calls,
            reasoning_content=self.reasoning or None,
            usage=self.usage,
        )
        return assistant_message

    async def handle(self, chunk: ChatCompletionChunk) -> None:
        await self.handle_usage(chunk)
        if not chunk.choices:
            return
        delta: ChoiceDelta = chunk.choices[0].delta
        await self.handle_thinking(delta)
        await self.handle_content(delta)
        await self.handle_tool_calls(delta)

    async def handle_thinking(self, delta: ChoiceDelta) -> None:
        reasoning_content = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning_content:
            self.reasoning += reasoning_content
            await self._emit_chunk(Chunk('reasoning_content', reasoning_content))

    async def handle_content(self, delta: ChoiceDelta) -> None:
        if delta.content:
            self.content += delta.content
            await self._emit_chunk(Chunk('content', delta.content))

    async def handle_tool_calls(self, delta: ChoiceDelta) -> None:
        if delta.tool_calls:
            for tc in delta.tool_calls:
                if tc.index not in self.tc_acc:
                    self.tc_acc[tc.index] = {
                        "id": "", "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                acc = self.tc_acc[tc.index]
                if tc.id:
                    acc["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        acc["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        acc["function"]["arguments"] += tc.function.arguments

    async def handle_usage(self, chunk: ChatCompletionChunk) -> None:
        if chunk.usage:
            self.usage = Usage(**chunk.usage.model_dump(include={'prompt_tokens', 'completion_tokens', 'total_tokens'}))

    def _to_tool_call(self, data: dict[str, Any]) -> ToolCall:
        return ToolCall(data["id"], data["type"], data["function"]["name"], data["function"]["arguments"])


class ToolHandler:
    def __init__(
        self,
        tool_timeout: float,
        _emit_chunk: EventFunction[Chunk],
        _emit_message: EventFunction[Message],
    ) -> None:
        self.tool_timeout = tool_timeout
        self._emit_chunk = _emit_chunk
        self._emit_message = _emit_message

    def _parse_tool_args(self, args: str | None) -> dict[str, Any] | None:
        if not args:
            return {}
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return None

    async def use_tools(
        self,
        msg: AssistantMessage,
        tool_map: dict[str, BaseTool],
        history: list[Message],
        ctx: ToolContext,
    ) -> None:
        if not msg.tool_calls:
            return
        tool_msgs = await asyncio.gather(*[self._run_tool(tc, tool_map, ctx) for tc in msg.tool_calls], return_exceptions=True)
        for tc, tool_msg in zip(msg.tool_calls, tool_msgs):
            if isinstance(tool_msg, BaseException):
                tool_msg = ToolMessage(tc.id, f"Error: {tool_msg}", tc.name, tc.arguments)
            history.append(tool_msg)
            await self._emit_message(tool_msg)
            await self._emit_chunk(Chunk('tool_result', tool_msg))

    async def _run_tool(self, tc: ToolCall, tool_map: dict[str, BaseTool], ctx: ToolContext) -> ToolMessage:
        name = tc.name
        args = tc.arguments
        tool = tool_map.get(name)
        if not tool:
            return ToolMessage(tc.id, f"Error: tool '{name}' not found", name, args)
        kwargs = self._parse_tool_args(args)
        if kwargs is None:
            return ToolMessage(tc.id, f"Error: tool '{name}' received invalid JSON arguments", name, args)
        timeout = tool.timeout if tool.timeout is not None else self.tool_timeout
        try:
            result = await asyncio.wait_for(tool.run(ctx=replace(ctx, tool_call_id=tc.id), **kwargs), timeout=timeout)
        except asyncio.TimeoutError:
            result = f"Error: tool '{name}' timed out after {timeout}s"
        except Exception as e:
            result = f"Error: {e}"
        return ToolMessage(tc.id, result, name, args)
