from typing import Any

from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta

from rqark_core.types.chat import AssistantMessage, Chunk, ToolCall, Usage


class ChunkHandler:
    def __init__(self, _emit_chunk):
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

    async def handle(self, chunk: ChatCompletionChunk):
        await self.handle_usage(chunk)
        if not chunk.choices:
            return
        delta: ChoiceDelta = chunk.choices[0].delta
        await self.handle_thinking(delta)
        await self.handle_content(delta)
        await self.handle_tool_calls(delta)

    async def handle_thinking(self, delta: ChoiceDelta):
        reasoning_content = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning_content:
            self.reasoning += reasoning_content
            await self._emit_chunk(Chunk('reasoning_content', reasoning_content))

    async def handle_content(self, delta: ChoiceDelta):
        if delta.content:
            self.content += delta.content
            await self._emit_chunk(Chunk('content', delta.content))

    async def handle_tool_calls(self, delta: ChoiceDelta):
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

    async def handle_usage(self, chunk: ChatCompletionChunk):
        if chunk.usage:
            self.usage = Usage(**chunk.usage.model_dump(include={'prompt_tokens', 'completion_tokens', 'total_tokens'}))

    def _to_tool_call(self, data: dict[str, Any]) -> ToolCall:
        return ToolCall(data["id"], data["type"], data["function"]["name"], data["function"]["arguments"])
