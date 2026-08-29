from collections.abc import Callable

from rqark_core.libs.event import BaseEventEmitter, EventFunction
from rqark_core.types.chat import Chunk, Message
from rqark_core.types.event import AgentCoreEventType, AgentPayload
from rqark_core.types.tool import PlanItem


class AgentCoreEventEmitter(BaseEventEmitter[AgentCoreEventType]):
    def __init__(self, agent_id: str = '', path: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.path = path

    def on_chunk(self) -> Callable[[EventFunction[AgentPayload[Chunk]]], EventFunction[AgentPayload[Chunk]]]:
        return self._on('chunk')

    def on_message(self) -> Callable[[EventFunction[AgentPayload[Message]]], EventFunction[AgentPayload[Message]]]:
        return self._on('message')

    def on_plan(self) -> Callable[[EventFunction[AgentPayload[list[PlanItem]]]], EventFunction[AgentPayload[list[PlanItem]]]]:
        return self._on('plan')

    async def _emit_chunk(self, chunk: Chunk) -> None:
        await self._emit('chunk', AgentPayload(self.agent_id, self.path, chunk))

    async def _emit_message(self, message: Message) -> None:
        await self._emit('message', AgentPayload(self.agent_id, self.path, message))

    async def _emit_plan(self, items: list[PlanItem]) -> None:
        await self._emit('plan', AgentPayload(self.agent_id, self.path, items))
