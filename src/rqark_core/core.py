import ssl
from collections.abc import Sequence
from typing import Any

import certifi
import httpx
from openai import AsyncOpenAI, AsyncStream

from rqark_core._core.event import AgentCoreEventEmitter
from rqark_core._core.stream import ChunkHandler, ToolHandler
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
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        http_client = httpx.AsyncClient(verify=ssl_context)
        return AsyncOpenAI(
            api_key=provider.api_key,
            base_url=provider.api_base,
            http_client=http_client,
            default_headers={},
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
        tool_handler = ToolHandler(self.tool_timeout, self._emit_chunk, self._emit_message)
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
                    await tool_handler.use_tools(msg, tool_map, history, ctx)
                except Exception as e:
                    error = e
                    await self._emit_chunk(Chunk('error', f'{type(error).__name__}: {error}'))
                    self._clean_history(history)
                    break
        return history[system_count:], error
