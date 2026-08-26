import traceback
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from rqark_core.types.chat import Chunk, Message, SubAgentChunk, SubAgentMessage
from rqark_core.types.tool import PlanItem

T = TypeVar("T")

class AgentCoreEventEmitter:
    def __init__(self):
        self._listeners: list[Callable[[Chunk], Awaitable[None]]] = []
        self._message_listeners: list[Callable[[Message], Awaitable[None]]] = []
        self._subagent_chunk_listeners: list[Callable[[SubAgentChunk], Awaitable[None]]] = []
        self._subagent_message_listeners: list[Callable[[SubAgentMessage], Awaitable[None]]] = []
        self._plan_listeners: list[Callable[[list[PlanItem]], Awaitable[None]]] = []

    def _on(self, listeners: list[Callable[[T], Awaitable[None]]]) -> Callable[[Callable[[T], Awaitable[None]]], Callable[[T], Awaitable[None]]]:
        def decorator(f: Callable[[T], Awaitable[None]]) -> Callable[[T], Awaitable[None]]:
            listeners.append(f)
            return f
        return decorator

    async def _emit(self, listeners: Sequence[Callable[[T], Awaitable[None]]], payload: T) -> None:
        for fn in listeners:
            try:
                await fn(payload)
            except Exception:
                traceback.print_exc()

    def on_chunk(self) -> Callable[[Callable[[Chunk], Awaitable[None]]], Callable[[Chunk], Awaitable[None]]]:
        return self._on(self._listeners)

    def on_message(self) -> Callable[[Callable[[Message], Awaitable[None]]], Callable[[Message], Awaitable[None]]]:
        return self._on(self._message_listeners)

    def on_subagent_chunk(self) -> Callable[[Callable[[SubAgentChunk], Awaitable[None]]], Callable[[SubAgentChunk], Awaitable[None]]]:
        return self._on(self._subagent_chunk_listeners)

    def on_subagent_message(self) -> Callable[[Callable[[SubAgentMessage], Awaitable[None]]], Callable[[SubAgentMessage], Awaitable[None]]]:
        return self._on(self._subagent_message_listeners)

    def on_plan(self) -> Callable[[Callable[[list[PlanItem]], Awaitable[None]]], Callable[[list[PlanItem]], Awaitable[None]]]:
        return self._on(self._plan_listeners)

    async def _emit_chunk(self, chunk: Chunk) -> None:
        await self._emit(self._listeners, chunk)

    async def _emit_message(self, message: Message) -> None:
        await self._emit(self._message_listeners, message)

    async def _emit_subagent_chunk(self, agent_id: str, chunk: Chunk) -> None:
        await self._emit(self._subagent_chunk_listeners, SubAgentChunk(agent_id, chunk))

    async def _emit_subagent_message(self, agent_id: str, message: Message) -> None:
        await self._emit(self._subagent_message_listeners, SubAgentMessage(agent_id, message))

    async def _emit_plan(self, items: list[PlanItem]) -> None:
        await self._emit(self._plan_listeners, items)
