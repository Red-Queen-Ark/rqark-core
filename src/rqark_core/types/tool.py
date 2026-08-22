from typing import Any
from abc import ABC, abstractmethod

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def display_key(self) -> str:
        return ''

    @abstractmethod
    def get_openai_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    async def run(self, **kwargs: Any) -> str: ...
