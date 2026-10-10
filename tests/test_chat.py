import uuid
from datetime import UTC, datetime

from rqark_core.core import AgentCore
from rqark_core.types.chat import AssistantMessage, SystemMessage, ToolMessage, UserMessage


def test_message_to_dict_carries_metadata():
    t = datetime(2026, 9, 7, 0, 0, tzinfo=UTC)
    user = UserMessage('hi', created_at=t, id='u1')
    assert user.to_dict() == {
        'role': 'user',
        'content': [{'type': 'text', 'text': 'hi'}],
        'created_at': t.isoformat(),
        'id': 'u1',
    }

    assistant = AssistantMessage('yo', reasoning_content='think step', created_at=t, id='a1')
    assert assistant.to_dict() == {
        'role': 'assistant',
        'content': 'yo',
        'created_at': t.isoformat(),
        'id': 'a1',
        'reasoning_content': 'think step',
    }

    tool = ToolMessage('c1', 'result', created_at=t, id='t1')
    assert tool.to_dict() == {
        'role': 'tool',
        'tool_call_id': 'c1',
        'content': 'result',
        'created_at': t.isoformat(),
        'id': 't1',
    }

    system = SystemMessage('sys', created_at=t, id='s1')
    assert system.to_dict() == {
        'role': 'system',
        'content': 'sys',
        'created_at': t.isoformat(),
        'id': 's1',
    }


def test_messages_default_created_at_is_utc_aware():
    for m in (UserMessage('hi'), ToolMessage('c1', 'r'), AssistantMessage('a'), SystemMessage('s')):
        assert m.created_at.tzinfo is not None


def test_messages_default_id_is_unique_uuid4():
    messages = [UserMessage('hi'), ToolMessage('c1', 'r'), AssistantMessage('a'), SystemMessage('s')]
    messages += [UserMessage('hi') for _ in range(50)]
    ids = [m.id for m in messages]
    assert len(set(ids)) == len(ids)
    for i in ids:
        assert uuid.UUID(i).version == 4


def test_to_api_message_strips_metadata():
    core = AgentCore()
    messages = [
        UserMessage('hi'),
        AssistantMessage('yo', reasoning_content='think'),
        AssistantMessage('tool-call', tool_calls=None),
        ToolMessage('c1', 'result'),
        SystemMessage('sys'),
    ]
    api = [core._to_api_message(m) for m in messages]
    assert api == [
        {'role': 'user', 'content': [{'type': 'text', 'text': 'hi'}]},
        {'role': 'assistant', 'content': 'yo'},
        {'role': 'assistant', 'content': 'tool-call'},
        {'role': 'tool', 'tool_call_id': 'c1', 'content': 'result'},
        {'role': 'system', 'content': 'sys'},
    ]
