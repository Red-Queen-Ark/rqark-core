import asyncio

from rqark_core.core import AgentCore
from rqark_core.types.provider import Provider
from rqark_core.types.chat import UserMessage, Chunk

async def main() -> None:
    provider = Provider('inhouse', 'api_key', 'http://127.0.0.1:8080', 0)
    messgaes = [
        UserMessage('你好')
    ]
    core = AgentCore(provider)
    @core.on_event()
    async def print_chunk(chunk: Chunk):
        print(chunk)
    new_messgaes = await core.chat(messgaes)

if __name__ == "__main__":
    asyncio.run(main())