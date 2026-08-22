import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from openai import AsyncOpenAI

from rqark_core.types.provider import Provider
from rqark_core.types.tool import BaseTool
from rqark_core.types.chat import Chunk, Message, AssistantMessage, ToolMessage, SystemMessage, ToolCall, Usage

class AgentCore:
    def __init__(self):
        self.timeout = 5
        self.tool_timeout = 30
        self.provider_retries = 3
        self.provider_retry_delay = 1
        self._listeners: list[Callable[[Chunk], Awaitable[None]]] = []
        self._message_listeners: list[Callable[[Message], Awaitable[None]]] = []

    async def chat(
        self, 
        provider: Provider, 
        messages: Sequence[Message], 
        system_prompts: Sequence[Message] = [], 
        tools: Sequence[BaseTool] = [],
    ) -> tuple[str | None, Sequence[Message]]:
        client = self._get_client(provider)
        tool_map = self._get_tool_map(tools)
        tool_prompts = self._get_tool_prompts(tools)
        history, system_count = self._build_history(provider, system_prompts, tool_prompts, messages)
        while True:
            params: dict[str, Any] = {
                "model": provider.model_name,
                "messages": [ m.to_dict() for m in history ],
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                params["tools"] = [t.get_openai_schema() for t in tools]
            last_err: Exception | None = None
            for attempt in range(self.provider_retries):
                try:
                    resp = await client.chat.completions.create(**params)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    if attempt < self.provider_retries - 1:
                        await asyncio.sleep(self.provider_retry_delay)
            if last_err is not None:
                return await self._fail(str(last_err), history, system_count)
            try:
                msg = await self._parse_stream(resp)
            except Exception as e:
                return await self._fail(str(e), history, system_count)
            history.append(msg)
            await self._emit_message(msg)
            if not msg.tool_calls:
                break
            tool_msgs = await asyncio.gather(*[self._run_tool(tc, tool_map) for tc in msg.tool_calls], return_exceptions=True)
            for tc, tool_msg in zip(msg.tool_calls, tool_msgs):
                if isinstance(tool_msg, BaseException):
                    tool_msg = ToolMessage(tc.id, f"Error: {tool_msg}", tc.name, tc.arguments)
                history.append(tool_msg)
                await self._emit_message(tool_msg)
                await self._emit_chuck(Chunk('tool_result', tool_msg))
        return None, history[system_count:]

    def on_chunk(self) -> Callable[[Callable[[Chunk], Awaitable[None]]], Callable[[Chunk], Awaitable[None]]]:
        def decorator(f: Callable[[Chunk], Awaitable[None]]) -> Callable[[Chunk], Awaitable[None]]:
            self._listeners.append(f)
            return f
        return decorator

    def on_message(self) -> Callable[[Callable[[Message], Awaitable[None]]], Callable[[Message], Awaitable[None]]]:
        def decorator(f: Callable[[Message], Awaitable[None]]) -> Callable[[Message], Awaitable[None]]:
            self._message_listeners.append(f)
            return f
        return decorator

    async def _emit_chuck(self, chunk: Chunk) -> None:
        for fn in self._listeners:
            await fn(chunk)

    async def _emit_message(self, message: Message) -> None:
        for fn in self._message_listeners:
            await fn(message)

    def _get_client(self, provider: Provider):
        return AsyncOpenAI(
            api_key=provider.api_key,
            base_url=provider.api_base,
            timeout=self.timeout,
        )

    def _get_tool_prompts(self, tools: Sequence[BaseTool]):
        tool_prompts = []
        for tool in tools:
            if tool.tool_prompt:
                prompt = SystemMessage(tool.tool_prompt)
                tool_prompts.append(prompt)
        return tool_prompts

    def _build_history(
        self,
        provider: Provider,
        system_prompts: Sequence[Message],
        tool_prompts: Sequence[Message],
        messages: Sequence[Message],
    ) -> tuple[list[Message], int]:
        head = list(system_prompts) + list(tool_prompts)
        if provider.combine and head:
            head = [SystemMessage("\n".join(m.content for m in head))]
        return head + list(messages), len(head)

    def _get_tool_map(self, tools: Sequence[BaseTool]):
        return {t.name: t for t in tools} if tools else {}

    async def _fail(self, err: str, history: list[Message], system_count: int) -> tuple[str, Sequence[Message]]:
        await self._emit_chuck(Chunk('error', err))
        self._clean_history(history)
        return err, history[system_count:]

    def _clean_history(self, history: list[Message]) -> list[Message]:
        while history and isinstance(history[-1], AssistantMessage) and history[-1].tool_calls:
            history.pop()
        return history

    async def _parse_stream(self, stream: Any) -> AssistantMessage:
        content = ""
        reasoning = ""
        usage: Usage | None = None
        tc_acc: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            if chunk.usage:
                usage = Usage(**chunk.usage.model_dump(include={'prompt_tokens', 'completion_tokens', 'total_tokens'}))
            if not chunk.choices:
                continue
            d = chunk.choices[0].delta
            if d.content:
                content += d.content
                await self._emit_chuck(Chunk('content', d.content))
            rc = getattr(d, "reasoning_content", None)
            if rc:
                reasoning += rc
                await self._emit_chuck(Chunk('reasoning_content', rc))
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

        tool_calls: list[ToolCall] | None = None
        if tc_acc:
            tool_calls = [self._to_tool_call(tc_acc[i]) for i in sorted(tc_acc)]
            await self._emit_chuck(Chunk('tool_calls', tool_calls))
        if usage:
            await self._emit_chuck(Chunk('usage', usage))
        assistant_message = AssistantMessage( content=content, tool_calls=tool_calls, reasoning_content=reasoning or None, usage=usage)
        return assistant_message

    def _to_tool_call(self, data: dict[str, Any]) -> ToolCall:
        return ToolCall(data["id"], data["type"], data["function"]["name"], data["function"]["arguments"])

    async def _run_tool(self, tc: ToolCall, tool_map: dict[str, BaseTool]) -> ToolMessage:
        name = tc.name
        args = tc.arguments
        tool = tool_map.get(name)
        if not tool:
            return ToolMessage(tc.id, f"Error: tool '{name}' not found", name, args)
        try:
            result = await asyncio.wait_for(tool.run(**(json.loads(args) if args else {})), timeout=self.tool_timeout)
        except asyncio.TimeoutError:
            result = f"Error: tool '{name}' timed out after {self.tool_timeout}s"
        except Exception as e:
            result = f"Error: {e}"
        return ToolMessage(tc.id, result, name, args)
