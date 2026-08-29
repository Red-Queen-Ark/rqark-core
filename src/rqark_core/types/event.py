from dataclasses import dataclass
from typing import Literal

type AgentCoreEventType = Literal['chunk', 'message', 'plan']

@dataclass
class AgentPayload[T]:
    agent_id: str
    path: tuple[str, ...]
    payload: T
