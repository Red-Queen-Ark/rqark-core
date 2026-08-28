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
from rqark_core.types.tool import BaseTool, PlanItem, ToolContext


class AgentCore(AgentCoreEventEmitter):
    def __init__(self, timeout: float = 300, tool_timeout: float = 120):
        super().__init__()
        self.timeout = timeout
        self.tool_timeout = tool_timeout
        self.plan_items: list[PlanItem] = []

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

    def _get_tool_prompts(self, tools: Sequence[BaseTool], ctx: ToolContext):
        tool_prompts = []
        for tool in tools:
            if content := tool.tool_prompt(ctx):
                tool_prompts.append(SystemMessage(content))
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
    async def _build_chat_params(self, provider: Provider, history: list[Message], tools: Sequence[BaseTool]):
        params: dict[str, Any] = {
            "model": provider.model_name,
            "messages": [ m.to_dict() for m in history ],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            params["tools"] = [t.get_openai_schema() for t in tools]
        if provider.reasoning_effort:
            params["reasoning_effort"] = provider.reasoning_effort
        if thinking := provider.thinking:
            params["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": thinking == "enabled"},
            }
        return params

    async def _parse_stream(self, stream: AsyncStream) -> AssistantMessage:
        handle_chunk = ChunkHandler(self._emit_chunk)
        async with stream:
            async for chunk in stream:
                await handle_chunk.handle(chunk)
        return await handle_chunk.message()

    async def chat(
        self,
        provider: Provider,
        messages: Sequence[Message],
        prompts: Sequence[BasePrompt] = [],
        tools: Sequence[BaseTool] = [],
    ) -> tuple[Sequence[Message], Exception | None]:
        error: Exception | None = None
        tool_map = self._get_tool_map(tools)
        ctx = ToolContext(core=self, provider=provider)
        tool_prompts = self._get_tool_prompts(tools, ctx)
        system_prompts = self._get_system_prompts(prompts)
        history, system_count = self._build_history(provider, system_prompts, tool_prompts, messages)
        async with self._get_client(provider) as client:
            while True:
                params = await self._build_chat_params(provider, history, tools)
                try:
                    resp: AsyncStream = await client.chat.completions.create(**params)
                    msg = await self._parse_stream(resp)
                    history.append(msg)
                    await self._emit_message(msg)
                    if not msg.tool_calls:
                        break
                    await self._use_tools(msg, tool_map, history, ctx)
                except Exception as e:
                    error = e
                    await self._emit_chunk(Chunk('error', f'{type(error).__name__}: {error}'))
                    self._clean_history(history)
                    break
        return history[system_count:], error

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

    async def _use_tools(
        self,
        msg: AssistantMessage,
        tool_map: dict[str, BaseTool],
        history: list[Message],
        ctx: ToolContext,
    ):
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
        try:
            result = await asyncio.wait_for(tool.run(ctx=ctx, **kwargs), timeout=self.tool_timeout)
        except asyncio.TimeoutError:
            result = f"Error: tool '{name}' timed out after {self.tool_timeout}s"
        except Exception as e:
            result = f"Error: {e}"
        return ToolMessage(tc.id, result, name, args)
