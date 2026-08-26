import asyncio
import json
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI, AsyncStream

from rqark_core._core.event import AgentCoreEventEmitter
from rqark_core._core.stream import ChunkHandler
from rqark_core.types.chat import AssistantMessage, Chunk, Message, SystemMessage, ToolCall, ToolMessage
from rqark_core.types.prompt import BasePrompt
from rqark_core.types.provider import Provider
from rqark_core.types.tool import BaseTool, set_parent_core


class AgentCore(AgentCoreEventEmitter):
    def __init__(self):
        super().__init__()
        self.timeout = 5
        self.tool_timeout = 120
        self.provider_retries = 3
        self.provider_retry_delay = 1

    """
    Getter
    """
    def _get_client(self, provider: Provider):
        return AsyncOpenAI(
            api_key=provider.api_key,
            base_url=provider.api_base,
            timeout=self.timeout,
        )

    def _get_system_prompts(self, prompts: Sequence[BasePrompt]):
        system_prompts = []
        _prompts = sorted(prompts, key=lambda p:p.priority)
        for prompt in _prompts:
            if content := prompt.get_messages():
                p = SystemMessage(content)
                system_prompts.append(p)
        return system_prompts

    def _get_tool_prompts(self, tools: Sequence[BaseTool]):
        tool_prompts = []
        for tool in tools:
            if tool.tool_prompt:
                prompt = SystemMessage(tool.tool_prompt)
                tool_prompts.append(prompt)
        return tool_prompts

    def _get_tool_map(self, tools: Sequence[BaseTool]):
        return {t.name: t for t in tools} if tools else {}

    """
    History
    """
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

    def _clean_history(self, history: list[Message]) -> list[Message]:
        while history and isinstance(history[-1], AssistantMessage) and history[-1].tool_calls:
            history.pop()
        return history
    """
    Chat Loop
    """
    async def _parse_stream(self, stream: AsyncStream) -> AssistantMessage:
        handle_chunk = ChunkHandler(self._emit_chunk)
        async for chunk in stream:
            await handle_chunk.handle(chunk)
        return await handle_chunk.message()

    async def chat(
        self,
        provider: Provider,
        messages: Sequence[Message],
        prompts: Sequence[BasePrompt] = [],
        tools: Sequence[BaseTool] = [],
    ) -> tuple[str | None, Sequence[Message]]:
        set_parent_core(self)
        client = self._get_client(provider)
        tool_map = self._get_tool_map(tools)
        tool_prompts = self._get_tool_prompts(tools)
        system_prompts = self._get_system_prompts(prompts)
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
            resp = None
            attempts = 0
            for attempt in range(self.provider_retries):
                attempts = attempt + 1
                try:
                    resp = await client.chat.completions.create(**params)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    if attempt < self.provider_retries - 1:
                        await asyncio.sleep(self.provider_retry_delay)
            if last_err is not None:
                return await self._fail(str(last_err), history, system_count, 'request', attempts, provider.model_name)
            if resp is None:
                return await self._fail('no provider attempt made', history, system_count, 'request', attempts, provider.model_name)
            try:
                msg = await self._parse_stream(resp)
            except Exception as e:
                return await self._fail(str(e), history, system_count, 'stream', attempts, provider.model_name)
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
                await self._emit_chunk(Chunk('tool_result', tool_msg))
        return None, history[system_count:]

    async def _fail(
        self,
        err: str,
        history: list[Message],
        system_count: int,
        stage: str = 'request',
        attempts: int = 1,
        model_name: str = '',
    ) -> tuple[str, Sequence[Message]]:
        await self._emit_chunk(Chunk('error', f'[stage={stage} attempts={attempts} model={model_name}] {err}'))
        self._clean_history(history)
        return err, history[system_count:]

    """
    Tool
    """
    def _parse_tool_args(self, args: str | None) -> dict[str, Any] | None:
        if not args:
            return {}
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return None

    async def _run_tool(self, tc: ToolCall, tool_map: dict[str, BaseTool]) -> ToolMessage:
        name = tc.name
        args = tc.arguments
        tool = tool_map.get(name)
        if not tool:
            return ToolMessage(tc.id, f"Error: tool '{name}' not found", name, args)
        kwargs = self._parse_tool_args(args)
        if kwargs is None:
            return ToolMessage(tc.id, f"Error: tool '{name}' received invalid JSON arguments", name, args)
        try:
            result = await asyncio.wait_for(tool.run(**kwargs), timeout=self.tool_timeout)
        except asyncio.TimeoutError:
            result = f"Error: tool '{name}' timed out after {self.tool_timeout}s"
        except Exception as e:
            result = f"Error: {e}"
        return ToolMessage(tc.id, result, name, args)
