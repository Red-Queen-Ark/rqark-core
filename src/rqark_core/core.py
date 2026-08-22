import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

from openai import AsyncOpenAI

from rqark_core.types.provider import Provider
from rqark_core.types.tool import BaseTool
from rqark_core.types.chat import Chunk, Message, AssistantMessage, ToolMessage, ToolCall


class AgentCore:
    def __init__(self, provider: Provider, tools: list[BaseTool] = []):
        self.timeout = 5
        self._listeners: list[Callable[[Chunk], Awaitable[None]]] = []
        self.set_tools(tools)
        self.set_provider(provider)
        
    def on_event(self) -> Callable[[Callable[[Chunk], Awaitable[None]]], Callable[[Chunk], Awaitable[None]]]:
        def decorator(f: Callable[[Chunk], Awaitable[None]]) -> Callable[[Chunk], Awaitable[None]]:
            self._listeners.append(f)
            return f
        return decorator

    async def _emit(self, chunk: Chunk) -> None:
        for fn in self._listeners:
            await fn(chunk)
    
    def set_tools(self, tools: list[BaseTool]):
        self.tools = tools
        self._tool_map = {t.name(): t for t in tools}
        
    def set_provider(self, provider: Provider) -> None:
        self.provider = provider
        self._client = AsyncOpenAI(
            api_key=provider.api_key,
            base_url=provider.api_base,
            timeout=self.timeout,
        )

    async def chat(self, messages: Sequence[Message]) -> Sequence[Message]:
        history = list(messages)
        while True:
            # params
            params: dict[str, Any] = {
                "model": self.provider.model_name,
                "messages": [ m.to_dict() for m in history ],
                "stream": True,
            }
            if self.tools:
                params["tools"] = [t.get_openai_schema() for t in self.tools]
            # chat
            resp = await self._client.chat.completions.create(**params)
            msg = await self._parse_stream(resp)
            history.append(msg)
            if not msg.tool_calls:
                break
            for tc in msg.tool_calls:
                tool_msg = await self._run_tool(tc)
                history.append(tool_msg)
                await self._emit(Chunk('tool_result', tool_msg))
        return history

    async def _parse_stream(self, stream: Any) -> AssistantMessage:
        content = ""
        reasoning = ""
        tc_acc: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue
            d = chunk.choices[0].delta
            if d.content:
                content += d.content
                await self._emit(Chunk('content', d.content))
            rc = getattr(d, "reasoning_content", None)
            if rc:
                reasoning += rc
                await self._emit(Chunk('reasoning_content', rc))
            if d.tool_calls:
                for tc in d.tool_calls:
                    if tc.index not in tc_acc:
                        tc_acc[tc.index] = {
                            "id": "", "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    acc = tc_acc[tc.index]
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            acc["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            acc["function"]["arguments"] += tc.function.arguments

        tool_calls: list[ToolCall] | None = (
            cast(list[ToolCall], [tc_acc[i] for i in sorted(tc_acc)]) or None
        )
        if tool_calls:
            await self._emit(Chunk('tool_calls', tool_calls))
        return AssistantMessage(
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning or None,
        )

    async def _run_tool(self, tc: ToolCall) -> ToolMessage:
        name = tc["function"]["name"]
        args = tc["function"]["arguments"]
        tool = self._tool_map.get(name)
        if not tool:
            return ToolMessage(tc["id"], f"Error: tool '{name}' not found", name, args)
        try:
            result = await tool.run(**(json.loads(args) if args else {}))
        except Exception as e:
            result = f"Error: {e}"
        return ToolMessage(tc["id"], result, name, args)
