from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

from rqark_core.types.provider import Provider

if TYPE_CHECKING:
    from rqark_core.core import AgentCore


@dataclass(frozen=True)
class PromptContext:
    core: 'AgentCore | None' = None
    provider: Provider | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class PromptDict(TypedDict):
    name: str
    params: dict[str, Any]


class BasePrompt(ABC):
    priority: int = 100

    @abstractmethod
    async def get_messages(self, ctx: PromptContext | None = None) -> str | None: ...

    def params(self) -> dict[str, Any]:
        return {}

    def to_dict(self) -> PromptDict:
        return {'name': type(self).__name__, 'params': self.params()}
