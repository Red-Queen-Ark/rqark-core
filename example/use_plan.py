import asyncio

from model import MODEL_NAME

from rqark_core.core import AgentCore
from rqark_core.tools import PlanUpdate
from rqark_core.types.chat import Message, UserMessage
from rqark_core.types.event import AgentPayload
from rqark_core.types.provider import Provider
from rqark_core.types.tool import PlanItem

provider = Provider(MODEL_NAME, 'http://127.0.0.1:8080', 0, 'api_key', combine=True)
core = AgentCore(agent_id='root')

tools = [PlanUpdate()]


@core.on_message()
async def print_msg(ev: AgentPayload[Message]):
    print(ev.payload.role, ev.payload.content)


@core.on_plan()
async def print_plan(ev: AgentPayload[list[PlanItem]]):
    print(ev.payload)


async def main() -> None:
    messages = [UserMessage('利用 plan_update 生成三個 items, 測試 1, 測試 2, 測試 3, 逐一切換狀態, 最後清空plan')]
    new_messages, error = await core.chat(provider=provider, messages=messages, tools=tools)


if __name__ == '__main__':
    asyncio.run(main())
