from collections.abc import Callable

from rqark_core.libs.event import BaseEventEmitter, EventFunction
from rqark_core.types.chat import Chunk, Message
from rqark_core.types.event import AgentCoreEventType
from rqark_core.types.tool import PlanItem


class AgentCoreEventEmitter(BaseEventEmitter[AgentCoreEventType]):
    def on_chunk(self) -> Callable[[EventFunction[Chunk]], EventFunction[Chunk]]:
        return self._on("chunk")

    def on_message(self) -> Callable[[EventFunction[Message]], EventFunction[Message]]:
        return self._on("message")

    def on_plan(self) -> Callable[[EventFunction[list[PlanItem]]], EventFunction[list[PlanItem]]]:
        return self._on("plan")

    async def _emit_chunk(self, chunk: Chunk) -> None:
        await self._emit("chunk", chunk)

    async def _emit_message(self, message: Message) -> None:
        await self._emit("message", message)

    async def _emit_plan(self, items: list[PlanItem]) -> None:
        await self._emit("plan", items)
