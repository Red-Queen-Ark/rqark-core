import traceback
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=str)

type EventFunction[T] = Callable[[T], Awaitable[None]]

class BaseEventEmitter[E]:
    def __init__(self) -> None:
        self._listeners: defaultdict[E, list[EventFunction[Any]]] = defaultdict(list)

    def _on(self, event_type: E) -> Callable[[EventFunction[T]], EventFunction[T]]:
        def decorator(f: EventFunction[T]) -> EventFunction[T]:
            self._listeners[event_type].append(f)
            return f
        return decorator

    async def _emit(self, event_type: E, payload: object) -> None:
        for fn in self._listeners[event_type]:
            try:
                await fn(payload)
            except Exception:
                traceback.print_exc()
