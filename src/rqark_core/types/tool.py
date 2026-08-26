from abc import ABC, abstractmethod
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from rqark_core.core import AgentCore

_parent_core: ContextVar['AgentCore | None'] = ContextVar('parent_core', default=None)

def set_parent_core(core: 'AgentCore') -> Token['AgentCore | None']:
    return _parent_core.set(core)

def reset_parent_core(token: Token['AgentCore | None']) -> None:
    _parent_core.reset(token)

class BaseTool(ABC):
    @property
    def parent_core(self) -> 'AgentCore | None':
        return _parent_core.get()

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def display_key(self) -> str:
        return ''

    @property
    def tool_prompt(self) -> str | None:
        return None

    @abstractmethod
    def get_openai_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    async def run(self, **kwargs: Any) -> str: ...

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
