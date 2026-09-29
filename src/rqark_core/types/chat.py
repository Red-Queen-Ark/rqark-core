from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal, TypedDict

type Role = Literal['system', 'user', 'assistant', 'tool']
type ChunkType = Literal['reasoning_content', 'content', 'tool_calls', 'tool_result', 'usage', 'error']


def _utc_now() -> datetime:
    return datetime.now(UTC)

@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

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
class UserContent:
    content: str
    type: Literal['text'] = 'text'

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "text": self.content,
        }

@dataclass
class UserImageContent:
    url: str
    type: Literal['image_url'] = 'image_url'

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "image_url": {"url": self.url },
        }

class UserMessageDict(TypedDict):
    role: str
    content:list[dict]
    created_at: str

@dataclass
class UserMessage:
    content: str
    role: Literal['user'] = 'user'
    created_at: datetime = field(default_factory=_utc_now)
    images: list[str] = field(default_factory=list)

    def to_dict(self) -> UserMessageDict:
        content: list[dict] = [ UserContent(self.content).to_dict() ]
        for img in self.images:
            content.append( UserImageContent(img).to_dict() )
        return {
            'role': self.role,
            'content': content,
            'created_at': self.created_at.isoformat(),
        }

@dataclass
class ToolMessage:
    tool_call_id: str
    content: str
    tool_name: str | None = None
    arguments: str | None = None
    role: Literal['tool'] = 'tool'
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, str]:
        return {
            'role': self.role,
            'tool_call_id': self.tool_call_id,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
        }

@dataclass
class AssistantMessage:
    content: str = ''
    tool_calls: list[ToolCall] | None = None
    reasoning_content: str | None = None
    usage: Usage | None = None
    role: Literal['assistant'] = 'assistant'
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict:
        d: dict = {
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
        }
        if self.tool_calls:
            d['tool_calls'] = [tc.to_dict() for tc in self.tool_calls]
        if self.reasoning_content:
            d['reasoning_content'] = self.reasoning_content
        return d

@dataclass
class SystemMessage:
    content: str
    role: Literal['system'] = 'system'
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, str]:
        return {
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
        }

type Message = UserMessage | ToolMessage | AssistantMessage | SystemMessage

@dataclass
class Chunk:
    type: ChunkType
    content: str | ToolMessage | list[ToolCall] | Usage

    def to_dict(self):
        content = self.content
        if isinstance(content, list):
            content = [ c.to_dict() for c in content ]
        elif isinstance(content, (Usage, ToolMessage)):
            content = content.to_dict()
        return {
            'type': self.type,
            'content': content
        }
