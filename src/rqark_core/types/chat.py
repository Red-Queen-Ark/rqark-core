from dataclasses import dataclass, asdict
from typing import Literal

type Role = Literal['system', 'user', 'assistant', 'tool']
type ChunkType = Literal['reasoning_content', 'content', 'tool_calls', 'tool_result', 'usage']

@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class ToolCall:
    id: str
    type: Literal['function']
    name: str
    arguments: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "function": {"name": self.name, "arguments": self.arguments},
        }

@dataclass
class UserMessage:
    content: str
    role: Literal['user'] = 'user'

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

@dataclass
class ToolMessage:
    tool_call_id: str
    content: str
    tool_name: str | None = None
    arguments: str | None = None
    role: Literal['tool'] = 'tool'

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }

@dataclass
class AssistantMessage:
    content: str = ''
    tool_calls: list[ToolCall] | None = None
    reasoning_content: str | None = None
    usage: Usage | None = None
    role: Literal['assistant'] = 'assistant'

    def to_dict(self) -> dict:
        d: dict = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        return d

@dataclass
class SystemMessage:
    content: str
    role: Literal['system'] = 'system'

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

type Message = UserMessage | ToolMessage | AssistantMessage | SystemMessage

@dataclass
class Chunk:
    type: ChunkType
    content: str | ToolMessage | list[ToolCall] | Usage
