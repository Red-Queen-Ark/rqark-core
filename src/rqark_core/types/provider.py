import re
from dataclasses import asdict, dataclass
from typing import Literal

DEFAULT_CONTEXT_WINDOW = 1_000_000
_CONTEXT_WINDOWS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r'^deepseek-v4-(pro|flash)$'), 1_048_576),
    (re.compile(r'^deepseek-(chat|reasoner)$'), 1_048_576),
    (re.compile(r'^deepseek-'), 1_048_576),
    (re.compile(r'^kimi-k3'), 1_000_000),
    (re.compile(r'^kimi-k2\.'), 262_144),
    (re.compile(r'^moonshot-v1-128k'), 128_000),
    (re.compile(r'^moonshot-v1-32k'), 32_000),
    (re.compile(r'^moonshot-v1-8k'), 8_000),
    (re.compile(r'^moonshot-'), 128_000),
    (re.compile(r'^mimo-'), 1_048_576),
    (re.compile(r'^qwen3\.7'), 1_000_000),
    (re.compile(r'^qwen3\.'), 262_144),
    (re.compile(r'^qwen3-'), 131_072),
    (re.compile(r'^qwen-'), 131_072),
    (re.compile(r'^grok-4\.5'), 500_000),
    (re.compile(r'^grok-4\.3'), 1_000_000),
    (re.compile(r'^grok-4\.'), 1_000_000),
    (re.compile(r'^grok-'), 1_000_000),
    (re.compile(r'^o3-mini'), 200_000),
    (re.compile(r'^o3-'), 200_000),
    (re.compile(r'^o4-mini'), 1_000_000),
    (re.compile(r'^o4-'), 1_000_000),
    (re.compile(r'^gpt-4o'), 128_000),
    (re.compile(r'^gpt-4\.'), 8_192),
    (re.compile(r'^gpt-3'), 16_385),
]


def resolve_context_window(model_name: str) -> int:
    for pattern, ctx in _CONTEXT_WINDOWS:
        if pattern.match(model_name):
            return ctx
    return DEFAULT_CONTEXT_WINDOW


@dataclass
class Provider:
    model_name: str
    api_base: str
    priority: int
    api_key: str | None = None
    id: str | None = None
    name: str = ''
    reasoning_effort: Literal['low', 'high', 'max'] | None = None
    thinking: Literal['enabled', 'disabled'] | None = None
    temperature: float | None = None
    top_p: float | None = None
    seed: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    combine: bool = False

    def __post_init__(self):
        if not self.name:
            self.name = self.model_name

    @property
    def context_window(self) -> int:
        return resolve_context_window(self.model_name)

    def to_dict(self):
        d = asdict(self)
        d['context_window'] = self.context_window
        return d
