from typing import Any, Literal
from abc import ABC, abstractmethod
from dataclasses import dataclass

class BaseTool(ABC):
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