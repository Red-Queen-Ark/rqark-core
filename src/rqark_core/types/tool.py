from typing import Any
from abc import ABC, abstractmethod

class BaseTool(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def get_openai_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    async def run(self, **kwargs: Any) -> str: ...
