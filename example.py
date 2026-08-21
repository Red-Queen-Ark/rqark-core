import asyncio

from rqark_core.core import AgentCore

async def main() -> None:
    core = AgentCore()
    await core.chat()

asyncio.run(main())