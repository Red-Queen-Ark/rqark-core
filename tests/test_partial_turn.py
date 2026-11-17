import asyncio
from contextlib import asynccontextmanager

import pytest

from rqark_core._core.stream import ChunkHandler
from rqark_core.core import STOPPED_TOOL_RESULT, AgentCore
from rqark_core.types.chat import AssistantMessage, ToolCall, ToolMessage, UserMessage
from rqark_core.types.provider import Provider


async def _noop_chunk(_chunk) -> None:
    return None


def _handler(content: str = '', reasoning: str = '') -> ChunkHandler:
    handler = ChunkHandler(_noop_chunk)
    handler.content = content
    handler.reasoning = reasoning
    return handler


def test_partial_turn_keeps_the_answer_the_user_watched():
    turn = AgentCore()._partial_turn([UserMessage('hi')], _handler('half an ans', 'because'), False)
    assert [type(m) for m in turn] == [UserMessage, AssistantMessage]
    assert turn[1].content == 'half an ans'
    assert turn[1].reasoning_content == 'because'


def test_partial_turn_marks_the_tool_results_the_stop_never_got():
    calls = [ToolCall('a', 'function', 'read_file', '{}'), ToolCall('b', 'function', 'grep', '{}')]
    history = [UserMessage('hi'), AssistantMessage(tool_calls=calls), ToolMessage('a', 'done', 'read_file', '{}')]
    turn = AgentCore()._partial_turn(history, None, True)
    assert [type(m) for m in turn] == [UserMessage, AssistantMessage, ToolMessage, ToolMessage]
    assert [m.tool_call_id for m in turn[2:]] == ['a', 'b']
    assert turn[2].content == 'done'
    assert turn[3].content == STOPPED_TOOL_RESULT


def test_partial_turn_does_not_repeat_a_message_already_appended():
    history = [UserMessage('hi'), AssistantMessage('done')]
    assert AgentCore()._partial_turn(history, _handler('done'), True) == history


def test_partial_turn_with_nothing_streamed_keeps_the_history():
    history = [UserMessage('hi'), AssistantMessage('thinking', tool_calls=[ToolCall('a', 'function', 'grep', '{}')]), ToolMessage('a', 'hit', 'grep', '{}')]
    turn = AgentCore()._partial_turn(history, _handler(), False)
    assert turn == history


@asynccontextmanager
async def _fake_client():
    class Completions:
        async def create(self, **_params):
            return object()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    yield Client()


async def test_chat_hands_a_cancelled_turn_back_through_partial(monkeypatch):
    core = AgentCore()
    partial: list = []

    async def cancelled_parse(stream, handle_chunk=None):
        handle_chunk.content = 'half an ans'
        raise asyncio.CancelledError

    monkeypatch.setattr(core, '_get_client', lambda _provider: _fake_client())
    monkeypatch.setattr(core, '_parse_stream', cancelled_parse)
    with pytest.raises(asyncio.CancelledError):
        await core.chat(Provider('m', 'http://x', 0, 'k'), [UserMessage('hi')], partial=partial)
    assert [type(m) for m in partial] == [UserMessage, AssistantMessage]
    assert partial[0].content == 'hi'
    assert partial[1].content == 'half an ans'


async def test_chat_leaves_partial_alone_when_no_one_asked(monkeypatch):
    core = AgentCore()

    async def cancelled_parse(stream, handle_chunk=None):
        raise asyncio.CancelledError

    monkeypatch.setattr(core, '_get_client', lambda _provider: _fake_client())
    monkeypatch.setattr(core, '_parse_stream', cancelled_parse)
    with pytest.raises(asyncio.CancelledError):
        await core.chat(Provider('m', 'http://x', 0, 'k'), [UserMessage('hi')])
