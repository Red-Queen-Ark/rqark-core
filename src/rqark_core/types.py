from dataclasses import dataclass
from typing import Literal, TypedDict

from rqark_core.libs.context_window import resolve_context_window

type Role = Literal['system', 'user', 'assistant', 'tool']

class FunctionCall(TypedDict):
    name: str
    arguments: str


class ToolCall(TypedDict):
    id: str
    type: Literal['function']
    function: FunctionCall


class ToolCallChunk(TypedDict, total=False):
    index: int
    id: str
    type: Literal['function']
    function: FunctionCall


@dataclass
class UserMessage:
    content: str
    role: Literal['user'] = 'user'


@dataclass
class ToolMessage:
    tool_call_id: str
    content: str
    tool_name: str | None = None
    arguments: str | None = None
    role: Literal['tool'] = 'tool'


@dataclass
class AssistantMessage:
    content: str = ''
    tool_calls: list[ToolCall] | None = None
    reasoning_content: str | None = None
    role: Literal['assistant'] = 'assistant'


@dataclass
class SystemMessage:
    content: str
    role: Literal['system'] = 'system'


type Message = UserMessage | ToolMessage | AssistantMessage | SystemMessage


@dataclass
class Chunk:
    type: Literal['reasoning_content', 'content', 'tool_calls']
    content: list | str


"""
provider types
"""
IS_THINK_MODEL: list[str] = ['deepseek-v4-pro', 'deepseek-v4-flash', 'kimi-k2.6', 'kimi-k3', 'grok-4.3', 'mimo-v2.5', 'qwen3', 'qwen-']

@dataclass
class Provider:
    model_name: str
    api_key: str
    api_base: str
    priority: int
    name: str = ''
    reasoning_effort: Literal['high', 'max'] | None = None
    thinking: Literal['enabled', 'disabled'] | None = None
    temperature: float | None = None
    top_p: float | None = None
    seed: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None

    def __post_init__(self):
        if not self.name:
            self.name = self.model_name

    @property
    def context_window(self) -> int:
        return resolve_context_window(self.model_name)

    @property
    def effective_thinking(self) -> Literal['enabled', 'disabled'] | None:
        return self.thinking if any(self.model_name.startswith(p) for p in IS_THINK_MODEL) else None
