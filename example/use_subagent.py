import asyncio

from model import MODEL_NAME

from rqark_core.core import AgentCore
from rqark_core.prompts import DateTimePrompt, PlatformPrompt, RolePrompt
from rqark_core.prompts.subagent import SubAgentPrompt
from rqark_core.tools import Grep, ListDir, ReadFile, SubAgent, WebFetch, WebSearch
from rqark_core.types.chat import Chunk, Message, ToolMessage, UserMessage
from rqark_core.types.event import AgentPayload
from rqark_core.types.provider import Provider

provider = Provider(MODEL_NAME, 'api_key', 'http://127.0.0.1:8080', 0, combine=True)

parent_prompts = [
    DateTimePrompt(),
    RolePrompt(),
    PlatformPrompt(),
]

subagent_prompts = [
    DateTimePrompt(),
    SubAgentPrompt(),
]

subagent_tools = [
    WebSearch(),
    WebFetch(),
    ReadFile(),
    Grep(),
    ListDir(),
]

core = AgentCore(agent_id='root')

subagent = SubAgent(subagent_prompts, subagent_tools)

tools = [
    subagent,
    WebSearch(),
    WebFetch(),
]

last_chunk_type = Chunk('reasoning_content', '')

def _sub_tag(ev: AgentPayload) -> str:
    return '/'.join(p[:8] for p in (*ev.path, ev.agent_id)) if ev.path else ''

@core.on_chunk()
async def print_chunk(ev: AgentPayload[Chunk]):
    global last_chunk_type
    chunk = ev.payload
    prefix = f'[sub {_sub_tag(ev)}] ' if _sub_tag(ev) else ''
    if last_chunk_type.type != chunk.type:
        print()
    if chunk.type == 'reasoning_content':
        print(f'{prefix}{chunk.content}', flush=True, end='')
    elif chunk.type == 'content':
        print(f'{prefix}{chunk.content}', flush=True, end='')
    elif chunk.type == 'tool_calls' and isinstance(chunk.content, list):
        for call in chunk.content:
            print(f'{prefix}{call.name} {call.arguments}')
    elif chunk.type == 'tool_result' and isinstance(chunk.content, ToolMessage):
        print(f'{prefix}{chunk.content.tool_name} {chunk.content.content}')
    elif chunk.type == 'error':
        print(f'{prefix}[error] {chunk.content}')
    last_chunk_type = chunk

@core.on_message()
async def print_message(ev: AgentPayload[Message]):
    prefix = f'[sub {_sub_tag(ev)}] ' if _sub_tag(ev) else ''
    print(f'{prefix}[message] {type(ev.payload).__name__}')

async def main() -> None:
    messages = [ UserMessage('用 subagent 幫我搜尋今日香港氣温') ]
    new_messages, error = await core.chat(provider=provider, messages=messages, prompts=parent_prompts, tools=tools)

if __name__ == "__main__":
    asyncio.run(main())
