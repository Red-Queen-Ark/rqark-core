from abc import ABC, abstractmethod
from typing import Any, TypedDict


class PromptDict(TypedDict):
    name: str
    params: dict[str, Any]


class BasePrompt(ABC):
    priority: int = 100

    @abstractmethod
    def get_messages(self) -> str | None: ...

    def params(self) -> dict[str, Any]:
        return {}

    def to_dict(self) -> PromptDict:
        return {'name': type(self).__name__, 'params': self.params()}
