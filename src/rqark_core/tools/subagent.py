from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from rqark_core.core import AgentCore
from rqark_core.types.chat import Chunk, Message, UserMessage
from rqark_core.types.event import AgentPayload
from rqark_core.types.prompt import BasePrompt
from rqark_core.types.tool import BaseTool, PlanItem, ToolContext

tool_prompt = """
## Subagent
Delegate aggressively to the subagent tool — it runs in its own context, keeping your main context clean and focused.
Use subagent when a task requires:
- Exploring multiple files or directories to understand code structure
- Searching the web and cross-referencing multiple sources
- Any investigation that would take 2+ tool calls
- Anything that risks cluttering your main context with too much data
Only keep it in main context if it is a single, trivial read (e.g. reading one known file).
You can also use multiple subagents in parallel when handling independent research tasks.
"""

class SubAgent(BaseTool):
    def __init__(self, prompts: Sequence[BasePrompt], tools: Sequence[BaseTool]):
        self.prompts = prompts
        self.tools = tools

    @property
    def name(self) -> str:
        return 'subagent'

    @property
    def display_key(self) -> str:
        return 'prompt'

    def tool_prompt(self, ctx: ToolContext | None = None) -> str:
        return tool_prompt

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Delegate an investigation or research task to an isolated subagent with its own context. The subagent runs independently, streams progress in real-time, and returns only the final result. Use this aggressively for multi-step research, exploring code, or any task that would clutter your main context.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'prompt': {'type': 'string', 'description': 'The task for the subagent. Be specific: what to investigate, what tools to use, what format the answer should be.'},
                    },
                    'required': ['prompt'],
                },
            },
        }

    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str:
        id = str(uuid4())
        prompt: str | None = kwargs.get('prompt')
        if prompt is None:
            raise TypeError('prompt is required')
        assert ctx is not None
        provider = ctx.provider
        assert provider is not None
        parent = ctx.core
        assert parent is not None
        core = AgentCore(agent_id=id, path=parent.path + (parent.agent_id,))

        @core.on_chunk()
        async def forward_chunk(ev: AgentPayload[Chunk]):
            await parent._emit('chunk', ev)

        @core.on_message()
        async def forward_message(ev: AgentPayload[Message]):
            await parent._emit('message', ev)

        @core.on_plan()
        async def forward_plan(ev: AgentPayload[list[PlanItem]]):
            await parent._emit('plan', ev)

        messages = [ UserMessage(prompt) ]
        new_messages, error = await core.chat(provider=provider, messages=messages, prompts=self.prompts, tools=self.tools)
        if error:
            return str(error)
        return new_messages[-1].content

    def params(self) -> dict[str, Any]:
        return {'prompts': [p.to_dict() for p in self.prompts], 'tools': [t.to_dict() for t in self.tools]}
