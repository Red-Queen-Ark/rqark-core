from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from rqark_core.types.provider import Provider

if TYPE_CHECKING:
    from rqark_core.core import AgentCore


@dataclass(frozen=True)
class ToolContext:
    core: 'AgentCore | None' = None
    provider: Provider | None = None
    tool_call_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class ToolDict(TypedDict):
    name: str
    params: dict[str, Any]


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def display_key(self) -> str:
        return ''

    @property
    def timeout(self) -> float | None:
        return None

    def tool_prompt(self, ctx: ToolContext | None = None) -> str | None:
        return None

    @abstractmethod
    def get_openai_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str: ...

    def params(self) -> dict[str, Any]:
        return {}

    def to_dict(self) -> ToolDict:
        return {'name': type(self).__name__, 'params': self.params()}


type PlanStatus = Literal['pending', 'in_progress', 'completed', 'cancelled']
ICONS_MAP: dict[PlanStatus, str] = {'pending': ' ', 'in_progress': '>', 'completed': 'x', 'cancelled': '-'}


@dataclass
class PlanItem:
    id: str
    content: str
    status: PlanStatus

    @property
    def icon(self):
        return ICONS_MAP.get(self.status, ' ')

    def to_dict(self):
        d = asdict(self)
        d['icon'] = self.icon
        return d
