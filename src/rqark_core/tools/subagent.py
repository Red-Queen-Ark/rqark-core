from uuid import uuid4
from typing import Any
from collections.abc import Sequence
from rqark_core.core import AgentCore
from rqark_core.types.tool import BaseTool
from rqark_core.types.prompt import BasePrompt
from rqark_core.types.provider import Provider
from rqark_core.types.chat import Chunk, Message, UserMessage

tool_prompt = """
## Subagent
Delegate aggressively to the subagent tool — it runs in its own context, keeping your main context clean and focused.
Use subagent when a task requires:
- Exploring multiple files or directories to understand code structure
- Searching the web and cross-referencing multiple sources
- Any investigation that would take 2+ tool calls
- Anything that risks cluttering your main context with too much data
Only keep it in main context if it is a single, trivial read (e.g. reading one known file).
The subagent runs independently with read-only tools by default; specify tool_allowlist if it needs write access (write_file, edit_file).
You can also use multiple subagents in parallel when handling independent research tasks.
"""

class SubAgent(BaseTool):
    def __init__(self, core: AgentCore, provider: Provider, prompts: Sequence[BasePrompt], tools: Sequence[BaseTool]):
        self.parent_core = core
        self.provider = provider
        self.prompts = prompts
        self.tools = tools

    @property
    def name(self) -> str:
        return 'subagent'

    @property
    def display_key(self) -> str:
        return 'prompt'
    
    @property
    def tool_prompt(self) -> str:
        return tool_prompt
    
    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Delegate an investigation or research task to an isolated subagent with its own context. The subagent runs independently, streams progress in real-time, and returns only the final result. Use this aggressively for multi-step research, exploring code, or any task that would clutter your main context. By default the subagent has read-only tools; use tool_allowlist to grant write tools (write_file, edit_file) when the task requires code modification.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'prompt': {'type': 'string', 'description': 'The task for the subagent. Be specific: what to investigate, what tools to use, what format the answer should be.'},
                    },
                    'required': ['prompt'],
                },
            },
        }
        
    async def run(self, **kwargs: Any) -> str:
        id = str(uuid4())
        prompt: str | None = kwargs.get('prompt')
        if prompt is None:
            raise TypeError('prompt is required')
        core = AgentCore()

        @core.on_chunk()
        async def forward_chunk(chunk: Chunk):
            await self.parent_core._emit_subagent_chunk(id, chunk)

        @core.on_message()
        async def forward_message(message: Message):
            await self.parent_core._emit_subagent_message(id, message)

        messgaes = [ UserMessage(prompt) ]
        error, new_messgaes = await core.chat(provider=self.provider, messages=messgaes, prompts=self.prompts, tools=self.tools)
        if error:
            return error
        return new_messgaes[-1].content