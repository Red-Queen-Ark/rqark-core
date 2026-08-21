import re

DEFAULT_CONTEXT_WINDOW = 1_000_000

_CONTEXT_WINDOWS: list[tuple[re.Pattern[str], int]] = [
    # DeepSeek
    (re.compile(r'^deepseek-v4-(pro|flash)$'), 1_048_576),
    (re.compile(r'^deepseek-(chat|reasoner)$'), 1_048_576),
    (re.compile(r'^deepseek-'), 1_048_576),  # catch-all for deepseek models
    # Kimi / Moonshot
    (re.compile(r'^kimi-k3'), 1_000_000),
    (re.compile(r'^kimi-k2\.'), 262_144),
    (re.compile(r'^moonshot-v1-128k'), 128_000),
    (re.compile(r'^moonshot-v1-32k'), 32_000),
    (re.compile(r'^moonshot-v1-8k'), 8_000),
    (re.compile(r'^moonshot-'), 128_000),  # catch-all
    # Xiaomi MiMo
    (re.compile(r'^mimo-'), 1_048_576),  # catch-all
    # Qwen / Alibaba
    (re.compile(r'^qwen3\.7'), 1_000_000),
    (re.compile(r'^qwen3\.'), 262_144),
    (re.compile(r'^qwen3-'), 131_072),
    (re.compile(r'^qwen-'), 131_072),  # catch-all
    # Grok / xAI
    (re.compile(r'^grok-4\.5'), 500_000),
    (re.compile(r'^grok-4\.3'), 1_000_000),
    (re.compile(r'^grok-4\.'), 1_000_000),
    (re.compile(r'^grok-'), 1_000_000),  # catch-all
    # OpenAI
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
