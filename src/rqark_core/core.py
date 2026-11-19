from __future__ import annotations

import asyncio
import ssl
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import certifi
import httpx

from rqark_core._core.event import AgentCoreEventEmitter
from rqark_core._core.stream import ChunkHandler, ToolHandler
from rqark_core.types.chat import AssistantMessage, Chunk, Message, SystemMessage, ToolMessage
from rqark_core.types.prompt import BasePrompt, PromptContext
from rqark_core.types.provider import Provider
from rqark_core.types.tool import BaseTool, PlanItem, ToolContext

if TYPE_CHECKING:
    from openai import AsyncOpenAI, AsyncStream

# Written in place of the result a cancelled turn never got, so the tool call the
# model asked for stays in the transcript instead of being dropped with the turn.
STOPPED_TOOL_RESULT = 'Error: the user stopped the turn before this tool returned'


class AgentCore(AgentCoreEventEmitter):
    def __init__(self, agent_id: str = '', path: tuple[str, ...] = (), timeout: float = 300, tool_timeout: float = 120, extras: dict[str, Any] | None = None):
        super().__init__(agent_id, path)
        self.timeout = timeout
        self.tool_timeout = tool_timeout
        self.extras: dict[str, Any] = extras if extras is not None else {}
        self.plan_items: list[PlanItem] = []

    """
    Getter
    """

    def _get_client(self, provider: Provider):
        from openai import AsyncOpenAI

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        http_client = httpx.AsyncClient(verify=ssl_context)
        return AsyncOpenAI(api_key=provider.api_key, base_url=provider.api_base, http_client=http_client, default_headers={}, timeout=self.timeout)

    def _spawn(self, agent_id: str, path: tuple[str, ...], tool_timeout: float, extras: dict[str, Any]) -> AgentCore:
        """Build the core a subagent runs on, on the same route as its parent.

        Subclasses that reach providers another way (a proxy, another SDK) override
        this; building an AgentCore directly would drop back to the default route.
        """
        return AgentCore(agent_id=agent_id, path=path, tool_timeout=tool_timeout, extras=extras)

    async def _get_system_prompts(self, prompts: Sequence[BasePrompt], ctx: PromptContext):
        system_prompts = []
        _prompts = sorted(prompts, key=lambda p: p.priority)
        for prompt in _prompts:
            if content := await prompt.get_messages(ctx):
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

    def _render_head(self, provider: Provider, system_prompts: Sequence[Message], tool_prompts: Sequence[Message]) -> list[Message]:
        head = list(system_prompts) + list(tool_prompts)
        if provider.combine and head:
            head = [SystemMessage('\n'.join(m.content for m in head))]
        return head

    def _build_history(self, provider: Provider, system_prompts: Sequence[Message], tool_prompts: Sequence[Message], messages: Sequence[Message]) -> tuple[list[Message], int]:
        head = self._render_head(provider, system_prompts, tool_prompts)
        return head + list(messages), len(head)

    def _clean_history(self, history: list[Message]) -> list[Message]:
        while history and isinstance(history[-1], AssistantMessage) and history[-1].tool_calls:
            history.pop()
        return history

    """
    Chat Loop
    """

    def _to_api_message(self, m: Message) -> dict[str, Any]:
        d: dict[str, Any] = dict(m.to_dict())
        d.pop('created_at', None)
        d.pop('reasoning_content', None)
        d.pop('id', None)
        # usage is recorded locally for accounting; the API rejects unknown message fields.
        d.pop('usage', None)
        return d

    async def _build_chat_params(self, provider: Provider, history: list[Message], tools: Sequence[BaseTool]):
        params: dict[str, Any] = {'model': provider.model_name, 'messages': [self._to_api_message(m) for m in history], 'stream': True, 'stream_options': {'include_usage': True}}
        if tools:
            params['tools'] = [t.get_openai_schema() for t in tools]
        if provider.reasoning_effort:
            params['reasoning_effort'] = provider.reasoning_effort
        if thinking := provider.thinking:
            params['extra_body'] = {'chat_template_kwargs': {'enable_thinking': thinking == 'enabled'}}
        return params

    async def _parse_stream(self, stream: AsyncStream, handle_chunk: ChunkHandler | None = None) -> AssistantMessage:
        handle_chunk = handle_chunk or ChunkHandler(self._emit_chunk)
        async with stream:
            async for chunk in stream:
                await handle_chunk.handle(chunk)
        return await handle_chunk.message()

    def _partial_turn(self, history: list[Message], handle_chunk: ChunkHandler | None, message_appended: bool) -> list[Message]:
        """The turn as it stood when the caller cancelled it.

        A stopped turn is stored and replayed to a provider by the next turn, so it
        has to be a valid transcript: the answer the user watched streaming never
        reached `history`, and a tool call without its result leaves the assistant
        message unusable. The streamed text is kept and the missing results are
        marked as interrupted, so neither the answer nor the tool record is lost.
        """
        turn = list(history)
        end = len(turn)
        while end and isinstance(turn[end - 1], ToolMessage):
            end -= 1
        last = turn[end - 1] if end else None
        if isinstance(last, AssistantMessage) and last.tool_calls:
            answered = {m.tool_call_id for m in turn[end:] if isinstance(m, ToolMessage)}
            turn.extend(ToolMessage(tc.id, STOPPED_TOOL_RESULT, tc.name, tc.arguments) for tc in last.tool_calls if tc.id not in answered)
        if not message_appended and handle_chunk is not None and (handle_chunk.content or handle_chunk.reasoning):
            turn.append(AssistantMessage(handle_chunk.content, reasoning_content=handle_chunk.reasoning or None))
        return turn

    async def chat(self, provider: Provider, messages: Sequence[Message], prompts: Sequence[BasePrompt] = [], tools: Sequence[BaseTool] = [], partial: list[Message] | None = None) -> tuple[Sequence[Message], Exception | None]:
        """Run one turn, through as many tool iterations as the model asks for.

        `partial` receives the turn built so far if the caller cancels this call:
        the turn only exists in this frame, so a stop would otherwise throw away
        every tool call and result it had already made.
        """
        error: Exception | None = None
        tool_map = self._get_tool_map(tools)
        ctx = ToolContext(core=self, provider=provider, extras=self.extras)
        prompt_ctx = PromptContext(core=self, provider=provider, extras=self.extras)
        system_prompts = await self._get_system_prompts(prompts, prompt_ctx)
        history, system_count = self._build_history(provider, system_prompts, [], messages)
        tool_handler = ToolHandler(self.tool_timeout, self._emit_chunk, self._emit_message)
        handle_chunk: ChunkHandler | None = None
        message_appended = True
        try:
            async with self._get_client(provider) as client:
                while True:
                    # Tool prompts are rebuilt every iteration: tools run inside this loop and may
                    # change the state they render (e.g. plan_update writes core.plan_items), so a
                    # head computed once per turn would be stale for the rest of the turn.
                    head = self._render_head(provider, system_prompts, self._get_tool_prompts(tools, ctx))
                    history[0:system_count] = head
                    system_count = len(head)
                    params = await self._build_chat_params(provider, history, tools)
                    try:
                        handle_chunk = ChunkHandler(self._emit_chunk)
                        message_appended = False
                        resp: AsyncStream = await client.chat.completions.create(**params)
                        msg = await self._parse_stream(resp, handle_chunk)
                        history.append(msg)
                        message_appended = True
                        await self._emit_message(msg)
                        if not msg.tool_calls:
                            break
                        await tool_handler.use_tools(msg, tool_map, history, ctx)
                    except Exception as e:
                        error = e
                        await self._emit_chunk(Chunk('error', f'{type(error).__name__}: {error}'))
                        self._clean_history(history)
                        break
        except asyncio.CancelledError:
            if partial is not None:
                partial[:] = self._partial_turn(history[system_count:], handle_chunk, message_appended)
            raise
        return history[system_count:], error
