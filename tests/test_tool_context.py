from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

from rqark_core._core.stream import ToolHandler
from rqark_core.core import AgentCore
from rqark_core.tools.subagent import SubAgent
from rqark_core.types.chat import AssistantMessage, Chunk, Message, ToolCall, ToolMessage, UserMessage
from rqark_core.types.provider import Provider
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


class ScriptedCore(AgentCore):
    def __init__(self, script: list[AssistantMessage], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.script = script

    def _get_client(self, provider: Provider):
        @asynccontextmanager
        async def factory():
            yield SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=self._create)))

        return factory()

    async def _create(self, **params: Any):
        return None

    async def _parse_stream(self, stream: Any) -> AssistantMessage:
        return self.script.pop(0)


async def test_chat_hands_extras_to_every_tool_call():
    tool = RecordingTool()
    extras = {'data_cloud': 'client', 'agent_id': 'agent-1'}
    core = ScriptedCore([AssistantMessage(content='', tool_calls=[ToolCall('call-1', 'function', 'record', '{}')]), AssistantMessage(content='done')], extras=extras)
    provider = Provider('model', 'key', 'http://test', 0)

    await core.chat(provider, [UserMessage('hi')], [], [tool])

    assert core.extras is extras
    assert tool.seen[0] is not None
    assert tool.seen[0].extras is extras


async def test_subagent_child_core_shares_extras(monkeypatch: Any):
    extras = {'data_cloud': 'client', 'agent_id': 'agent-1'}
    seen: list[Any] = []

    class ChildCore(AgentCore):
        def __init__(self, **kwargs: Any) -> None:
            seen.append(kwargs.get('extras'))
            super().__init__(**kwargs)

        async def chat(self, provider: Any, messages: Any, prompts: Any = (), tools: Any = ()):
            return [AssistantMessage('child result')], None

    monkeypatch.setattr('rqark_core.tools.subagent.AgentCore', ChildCore)

    parent = AgentCore(extras=extras)
    tool = SubAgent([], [])
    provider = Provider('model', 'key', 'http://test', 0)
    result = await tool.run(ctx=ToolContext(core=parent, provider=provider, extras=extras), prompt='go')

    assert result == 'child result'
    assert seen == [extras]
