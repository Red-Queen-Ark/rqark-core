import asyncio

from model import MODEL_NAME

from rqark_core.core import AgentCore
from rqark_core.types.chat import Chunk, Message, ToolMessage, UserMessage
from rqark_core.types.event import AgentPayload
from rqark_core.types.provider import Provider

provider = Provider(MODEL_NAME, 'http://127.0.0.1:8080', 0, 'api_key', combine=True)
core = AgentCore(agent_id='root')

last_chunk_type = Chunk('reasoning_content', '')


@core.on_chunk()
async def print_chunk(ev: AgentPayload[Chunk]):
    global last_chunk_type
    chunk = ev.payload
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
async def print_message(ev: AgentPayload[Message]):
    print(f'[message] {type(ev.payload).__name__}')


async def main() -> None:
    messages = [UserMessage('你好')]
    new_messages, error = await core.chat(provider=provider, messages=messages)


if __name__ == '__main__':
    asyncio.run(main())
