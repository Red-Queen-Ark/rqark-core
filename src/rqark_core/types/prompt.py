from abc import ABC, abstractmethod

class BasePrompt(ABC):
    priority: int = 100
    
    @abstractmethod
    def get_messages(self) -> str | None: ...
