# rqark-core

The engine of the RQArk Ecology System

A stateless agent engine for Python. Ships a basic agent toolkit, a set of base prompts, and a unified streaming interface for agent events.

## Why rqark-core

The `openai` package gives you a client. This adds the loop on top of it — same protocol, same streaming, nothing replaced.

- **Cleaner event flow** — `@core.on_xx`, in the spirit of flask / fastapi
- **Live prompts** — the latest prompt content is injected on every turn

## Installation

Requires Python 3.14+.

```bash
uv add rqark-core
# or
pip install rqark-core
```

## Quick Start

```python
import asyncio
from rqark_core.core import AgentCore
from rqark_core.types.provider import Provider
from rqark_core.types.event import AgentPayload
from rqark_core.types.chat import Chunk, Message, UserMessage
from rqark_core.tools import WebFetch, WebSearch
from rqark_core.prompts import DateTimePrompt

provider = Provider(model_name='gpt-5', api_base='https://api.openai.com/v1', priority=0, api_key='sk-...')

core = AgentCore()


@core.on_chunk()
async def print_chunk(event: AgentPayload[Chunk]):
    print(event.payload)


@core.on_message()
async def print_message(event: AgentPayload[Message]):
    print(event.payload)


prompts = [DateTimePrompt()]
tools = [WebSearch(), WebFetch()]


async def main():
    messages = [UserMessage('What news in Hong Kong?')]
    history, error = await core.chat(provider, messages, prompts=prompts, tools=tools)
    if error:
        print('failed:', error)


asyncio.run(main())
```

## Events

- `on_chunk`
- `on_message`
- `on_plan`

## Prompts

### Dynamic injection

Prompt content is rebuilt on every turn — `DateTimePrompt` calls `now()`, for example.
If no `AGENTS.md` is found, `AgentsMdPrompt` hides its content to save context; `GitProjectPrompt` behaves the same way.

### General

- `DateTimePrompt`
- `PlatformPrompt`
- `WorkspacePrompt`
- `AgentsMdPrompt`
- `GitProjectPrompt`

### Roleplay

- `RolePrompt`
- `CharacterPrompt`

### Other

- `AntiSycophancyPrompt`
- `SubAgentPrompt`

## Tools

### Files

- `ReadFile`
- `WriteFile`
- `EditFile`
- `ListDir`
- `Grep`

### Search

- `WebSearch`
- `WebFetch`

### Git

- `GitHub`
- `GitLab`
- `Gitea`

### Other

- `Exec`
- `PlanUpdate`
- `SubAgent`
