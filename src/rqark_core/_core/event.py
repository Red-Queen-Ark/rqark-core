from collections.abc import Callable

from rqark_core.libs.event import BaseEventEmitter, EventFunction
from rqark_core.types.chat import Chunk, Message, SubAgentChunk, SubAgentMessage
from rqark_core.types.event import AgentCoreEventType
from rqark_core.types.tool import PlanItem


class AgentCoreEventEmitter(BaseEventEmitter[AgentCoreEventType]):
    def on_chunk(self) -> Callable[[EventFunction[Chunk]], EventFunction[Chunk]]:
        return self._on("chunk")

    def on_message(self) -> Callable[[EventFunction[Message]], EventFunction[Message]]:
        return self._on("message")

    def on_subagent_chunk(self) -> Callable[[EventFunction[SubAgentChunk]], EventFunction[SubAgentChunk]]:
        return self._on("subagent_chunk")

    def on_subagent_message(self) -> Callable[[EventFunction[SubAgentMessage]], EventFunction[SubAgentMessage]]:
        return self._on("subagent_message")

    def on_plan(self) -> Callable[[EventFunction[list[PlanItem]]], EventFunction[list[PlanItem]]]:
        return self._on("plan")

    async def _emit_chunk(self, chunk: Chunk) -> None:
        await self._emit("chunk", chunk)

    async def _emit_message(self, message: Message) -> None:
        await self._emit("message", message)

    async def _emit_subagent_chunk(self, agent_id: str, chunk: Chunk) -> None:
        await self._emit("subagent_chunk", SubAgentChunk(agent_id, chunk))

    async def _emit_subagent_message(self, agent_id: str, message: Message) -> None:
        await self._emit("subagent_message", SubAgentMessage(agent_id, message))

    async def _emit_plan(self, items: list[PlanItem]) -> None:
        await self._emit("plan", items)
