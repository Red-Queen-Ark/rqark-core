from typing import Any

from rqark_core._core.stream import ToolHandler
from rqark_core.types.chat import AssistantMessage, Chunk, Message, ToolCall, ToolMessage
from rqark_core.types.tool import BaseTool, ToolContext


async def _noop_chunk(chunk: Chunk) -> None:
    return None


async def _noop_message(message: Message) -> None:
    return None


class RecordingTool(BaseTool):
    def __init__(self) -> None:
        self.seen: list[ToolContext | None] = []

    @property
    def name(self) -> str:
        return 'record'

    def get_openai_schema(self) -> dict[str, Any]:
        return {}

    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str:
        self.seen.append(ctx)
        return 'ok'


async def test_run_tool_exposes_the_call_id_without_mutating_the_shared_context():
    tool = RecordingTool()
    handler = ToolHandler(5, _noop_chunk, _noop_message)
    shared = ToolContext()
    msg = AssistantMessage(content='', tool_calls=[ToolCall('call-1', 'function', 'record', '{}')])
    history: list[Message] = []
    await handler.use_tools(msg, {'record': tool}, history, shared)
    assert tool.seen[0] is not None
    assert tool.seen[0].tool_call_id == 'call-1'
    assert shared.tool_call_id is None
    assert len(history) == 1
    result = history[0]
    assert isinstance(result, ToolMessage)
    assert (result.tool_call_id, result.content, result.tool_name, result.arguments) == ('call-1', 'ok', 'record', '{}')
