import asyncio

from model import MODEL_NAME

from rqark_core.core import AgentCore
from rqark_core.prompts import DateTimePrompt, PlatformPrompt, RolePrompt
from rqark_core.prompts.subagent import SubAgentPrompt
from rqark_core.tools import Grep, ListDir, ReadFile, SubAgent, WebFetch, WebSearch
from rqark_core.types.chat import Chunk, Message, SubAgentChunk, SubAgentMessage, ToolMessage, UserMessage
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

core = AgentCore()

subagent = SubAgent(subagent_prompts, subagent_tools)

tools = [
    subagent,
    WebSearch(),
    WebFetch(),
]

last_chunk_type = Chunk('reasoning_content', '')

@core.on_chunk()
async def print_chunk(chunk: Chunk):
    global last_chunk_type
    if last_chunk_type.type != chunk.type:
        print()
    if chunk.type == 'reasoning_content':
        print(chunk.content, flush=True, end='')
    elif chunk.type == 'content':
        print(chunk.content, flush=True, end='')
    elif chunk.type == 'tool_calls' and isinstance(chunk.content, list):
        for call in chunk.content:
            print(call.name, call.arguments)
    elif chunk.type == 'tool_result' and isinstance(chunk.content, ToolMessage):
        print(chunk.content.tool_name, chunk.content.content)
    elif chunk.type == 'error':
        print(f'[error] {chunk.content}')
    last_chunk_type = chunk

@core.on_message()
async def print_message(message: Message):
    print(f'[message] {type(message).__name__}')

@core.on_subagent_chunk()
async def print_subagent_chunk(sub_chunk: SubAgentChunk):
    c = sub_chunk.chunk
    if c.type == 'content':
        print(f'[sub {sub_chunk.id[:8]}] {c.content}', flush=True, end='')
    elif c.type == 'reasoning_content':
        print(f'[sub {sub_chunk.id[:8]}] {c.content}', flush=True, end='')
    elif c.type == 'tool_calls' and isinstance(c.content, list):
        for call in c.content:
            print(f'[sub {sub_chunk.id[:8]}] {call.name} {call.arguments}')
    elif c.type == 'tool_result' and isinstance(c.content, ToolMessage):
        print(f'[sub {sub_chunk.id[:8]}] {c.content.tool_name} {c.content.content}')
    elif c.type == 'error':
        print(f'[sub {sub_chunk.id[:8]}] [error] {c.content}')

@core.on_subagent_message()
async def print_subagent_message(sub_msg: SubAgentMessage):
    print(f'[sub {sub_msg.id[:8]}] [message] {type(sub_msg.message).__name__}')

async def main() -> None:
    messages = [ UserMessage('用 subagent 幫我搜尋今日香港氣温') ]
    error, new_messages = await core.chat(provider=provider, messages=messages, prompts=parent_prompts, tools=tools)

if __name__ == "__main__":
    asyncio.run(main())
