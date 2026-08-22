import asyncio
from typing import Sequence

from rqark_core.core import AgentCore
from rqark_core.types.provider import Provider
from rqark_core.types.chat import UserMessage, SystemMessage, ToolMessage, Chunk
from rqark_core.prompts import DateTimePrompt, RolePrompt, PlatformPrompt
from rqark_core.tools import WebSearch, WebFetch

provider = Provider('inhouse', 'api_key', 'http://127.0.0.1:8080', 0)

prompts = [
    DateTimePrompt(),
    RolePrompt(),
    PlatformPrompt(),
]
prompts.sort(key=lambda p:p.priority)

tools = [
    WebSearch(), 
    WebFetch(),
]

core = AgentCore(provider, tools)

last_chunk_type = Chunk('reasoning_content', '')

@core.on_event()
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
    last_chunk_type = chunk
        
async def main() -> None:
    messgaes = [ UserMessage('今日天氣') ]
    system_prompts = [ SystemMessage('') ]
    for prompt in prompts:
        if p := prompt.get_messages():
            system_prompts[0].content += p
    new_messgaes = await core.chat(messgaes, system_prompts)

if __name__ == "__main__":
    asyncio.run(main())
