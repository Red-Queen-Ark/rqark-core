from datetime import UTC, datetime

from rqark_core.core import AgentCore
from rqark_core.types.chat import AssistantMessage, SystemMessage, ToolMessage, UserMessage


def test_message_to_dict_carries_metadata():
    t = datetime(2026, 9, 7, 0, 0, tzinfo=UTC)
    user = UserMessage('hi', created_at=t)
    assert user.to_dict() == {'role': 'user', 'content': 'hi', 'created_at': t.isoformat()}

    assistant = AssistantMessage('yo', reasoning_content='think step', created_at=t)
    assert assistant.to_dict() == {
        'role': 'assistant',
        'content': 'yo',
        'created_at': t.isoformat(),
        'reasoning_content': 'think step',
    }

    tool = ToolMessage('c1', 'result', created_at=t)
    assert tool.to_dict() == {'role': 'tool', 'tool_call_id': 'c1', 'content': 'result', 'created_at': t.isoformat()}

    system = SystemMessage('sys', created_at=t)
    assert system.to_dict() == {'role': 'system', 'content': 'sys', 'created_at': t.isoformat()}


def test_messages_default_created_at_is_utc_aware():
    for m in (UserMessage('hi'), ToolMessage('c1', 'r'), AssistantMessage('a'), SystemMessage('s')):
        assert m.created_at.tzinfo is not None


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
        {'role': 'user', 'content': 'hi'},
        {'role': 'assistant', 'content': 'yo'},
        {'role': 'assistant', 'content': 'tool-call'},
        {'role': 'tool', 'tool_call_id': 'c1', 'content': 'result'},
        {'role': 'system', 'content': 'sys'},
    ]
