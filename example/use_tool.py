import asyncio
from rqark_core.core import AgentCore
from rqark_core.types.provider import Provider
from rqark_core.types.chat import UserMessage, SystemMessage, ToolMessage, Chunk, Message
from rqark_core.prompts import DateTimePrompt, RolePrompt, PlatformPrompt
from rqark_core.tools import WebSearch, WebFetch

provider = Provider('inhouse', 'api_key', 'http://127.0.0.1:8080', 0, combine=True)

prompts = [
    DateTimePrompt(),
    RolePrompt(),
    PlatformPrompt(),
]

tools = [
    WebSearch(), 
    WebFetch(),
]

core = AgentCore()

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

async def main() -> None:
    messgaes = [ UserMessage('今日天氣') ]
    error, new_messgaes = await core.chat(provider=provider, messages=messgaes, prompts=prompts, tools=tools)

if __name__ == "__main__":
    asyncio.run(main())
