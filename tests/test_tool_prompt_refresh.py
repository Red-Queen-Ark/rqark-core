import json
from typing import Any

from rqark_core.core import AgentCore
from rqark_core.types.chat import AssistantMessage, SystemMessage, ToolCall
from rqark_core.types.provider import Provider
from rqark_core.types.tool import BaseTool


class _MutableTool(BaseTool):
    """A tool whose prompt renders mutable core state, like plan_update does."""

    @property
    def name(self) -> str:
        return 'mutable'

    def tool_prompt(self, ctx: Any = None) -> str:
        state = getattr(ctx.core, 'value', 'EMPTY')
        return f'## State\n{state}'

    def get_openai_schema(self) -> dict[str, Any]:
        return {'type': 'function', 'function': {'name': self.name, 'description': '', 'parameters': {'type': 'object', 'properties': {}}}}

    async def run(self, ctx: Any = None, **kwargs: Any) -> str:
        ctx.core.value = kwargs['value']
        return 'ok'


class _Completions:
    @staticmethod
    async def create(**kwargs: Any) -> object:
        return object()


class _Chat:
    completions = _Completions()


class _Client:
    chat = _Chat()

    async def __aenter__(self) -> '_Client':
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


def _patch(monkeypatch, script: list[AssistantMessage], sent: list[list[SystemMessage]]) -> None:
    async def parse_stream(self, stream):
        return script.pop(0)

    def get_client(self, provider):
        return _Client()

    async def build_chat_params(self, provider, history, tools):
        sent.append([m for m in history if isinstance(m, SystemMessage)])
        return {'model': 'fake', 'messages': [], 'stream': True}

    monkeypatch.setattr(AgentCore, '_parse_stream', parse_stream)
    monkeypatch.setattr(AgentCore, '_get_client', get_client)
    monkeypatch.setattr(AgentCore, '_build_chat_params', build_chat_params)


async def test_tool_prompt_is_rebuilt_after_a_tool_changes_core_state(monkeypatch):
    script = [AssistantMessage('', tool_calls=[ToolCall('c1', 'function', 'mutable', json.dumps({'value': 'NEW'}))]), AssistantMessage('done')]
    sent: list[list[SystemMessage]] = []
    _patch(monkeypatch, script, sent)

    core = AgentCore()
    messages, error = await core.chat(Provider('m', 'http://x', 0, 'k'), [], [], [_MutableTool()])

    assert error is None
    assert [type(m).__name__ for m in messages] == ['AssistantMessage', 'ToolMessage', 'AssistantMessage']
    assert len(sent) == 2
    assert 'EMPTY' in sent[0][0].content
    assert 'NEW' in sent[1][0].content


async def test_tool_prompt_rebuild_keeps_the_history_tail(monkeypatch):
    script = [AssistantMessage('', tool_calls=[ToolCall('c1', 'function', 'mutable', json.dumps({'value': 'NEW'}))]), AssistantMessage('done')]
    sent: list[list[SystemMessage]] = []
    _patch(monkeypatch, script, sent)

    core = AgentCore()
    messages, _ = await core.chat(Provider('m', 'http://x', 0, 'k'), [], [], [_MutableTool()])

    assert len(sent[0]) == 1 and len(sent[1]) == 1
    assert [type(m).__name__ for m in messages] == ['AssistantMessage', 'ToolMessage', 'AssistantMessage']
    assert len(sent) == 2


async def test_combined_head_is_rebuilt_as_a_single_system_message(monkeypatch):
    script = [AssistantMessage('', tool_calls=[ToolCall('c1', 'function', 'mutable', json.dumps({'value': 'NEW'}))]), AssistantMessage('done')]
    sent: list[list[SystemMessage]] = []
    _patch(monkeypatch, script, sent)

    core = AgentCore()
    await core.chat(Provider('m', 'http://x', 0, 'k', combine=True), [], [], [_MutableTool()])

    assert len(sent[0]) == 1 and len(sent[1]) == 1
    assert 'EMPTY' in sent[0][0].content
    assert 'NEW' in sent[1][0].content


async def test_turn_without_tool_calls_sends_one_iteration(monkeypatch):
    script = [AssistantMessage('hi')]
    sent: list[list[SystemMessage]] = []
    _patch(monkeypatch, script, sent)

    core = AgentCore()
    messages, error = await core.chat(Provider('m', 'http://x', 0, 'k'), [], [], [_MutableTool()])

    assert error is None
    assert [m.content for m in messages] == ['hi']
    assert len(sent) == 1
