import asyncio
from rqark_core.core import AgentCore
from rqark_core.types.chat import UserMessage, Message
from rqark_core.types.provider import Provider
from rqark_core.types.tool import PlanItem
from rqark_core.tools import PlanUpdate


provider = Provider('inhouse', 'api_key', 'http://127.0.0.1:8080', 0, combine=True)
core = AgentCore()

tools = [ PlanUpdate() ]

@core.on_message()
async def print_msg(msg: Message):
    print(msg.role, msg.content)

@core.on_plan()
async def print_plan(plan_items: list[PlanItem]):
    print(plan_items)

async def main() -> None:
    messgaes = [ UserMessage('利用 plan_update 生成三個 items, 測試 1, 測試 2, 測試 3, 逐一切換狀態, 最後清空plan') ]
    error, new_messgaes = await core.chat(provider=provider, messages=messgaes, tools=tools)

if __name__ == "__main__":
    asyncio.run(main())