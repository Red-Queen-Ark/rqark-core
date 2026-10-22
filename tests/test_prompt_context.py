from typing import Any

from rqark_core.core import AgentCore
from rqark_core.tools.subagent import SubAgent
from rqark_core.types.chat import AssistantMessage, UserMessage
from rqark_core.types.prompt import BasePrompt, PromptContext
from rqark_core.types.provider import Provider
from rqark_core.types.tool import ToolContext


class RecordingPrompt(BasePrompt):
    priority = 10

    def __init__(self) -> None:
        self.seen: list[PromptContext | None] = []

    async def get_messages(self, ctx: PromptContext | None = None) -> str | None:
        self.seen.append(ctx)
        return 'recorded'


class EchoTool:
    name = 'noop'


class ScriptedCore(AgentCore):
    def __init__(self, script: list[AssistantMessage], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.script = script
        self.system_messages: list[str] = []

    def _get_client(self, provider: Provider):
        from types import SimpleNamespace

        class _Factory:
            def __init__(self, outer: 'ScriptedCore') -> None:
                self.outer = outer

            async def __aenter__(self):
                return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=self.outer._create)))

            async def __aexit__(self, *args: Any) -> None:
                return None

        return _Factory(self)

    async def _create(self, **params: Any):
        return None

    async def _parse_stream(self, stream: Any) -> AssistantMessage:
        return self.script.pop(0)


async def test_system_prompts_receive_the_shared_extras():
    extras = {'data_cloud': 'client', 'agent_id': 'agent-1'}
    prompt = RecordingPrompt()
    core = ScriptedCore([AssistantMessage(content='done')], extras=extras)
    provider = Provider('model', 'http://test', 0, 'key')

    await core.chat(provider, [UserMessage('hi')], [prompt], [])

    assert prompt.seen[0] is not None
    assert prompt.seen[0].extras is extras
    assert prompt.seen[0].core is core
    assert prompt.seen[0].provider is provider


async def test_prompt_context_defaults_to_empty_extras_and_no_core():
    ctx = PromptContext()
    assert ctx.extras == {}
    assert ctx.core is None
    assert ctx.provider is None


async def test_subagent_prompts_also_see_the_extras(monkeypatch: Any):
    extras = {'data_cloud': 'client', 'agent_id': 'agent-1'}
    parent_prompt = RecordingPrompt()
    child_prompt = RecordingPrompt()

    class ChildCore(AgentCore):
        async def chat(self, provider: Any, messages: Any, prompts: Any = (), tools: Any = ()):
            for prompt in prompts:
                await prompt.get_messages(PromptContext(core=self, provider=provider, extras=self.extras))
            return [AssistantMessage('child result')], None

    class ParentCore(AgentCore):
        def _spawn(self, agent_id: str, path: tuple[str, ...], tool_timeout: float, extras: dict[str, Any]) -> AgentCore:
            return ChildCore(agent_id=agent_id, path=path, tool_timeout=tool_timeout, extras=extras)

    parent = ParentCore(extras=extras)
    tool = SubAgent([child_prompt], [])
    provider = Provider('model', 'http://test', 0, 'key')
    await tool.run(ctx=ToolContext(core=parent, provider=provider, extras=extras), prompt='go')

    assert parent_prompt.seen == []
    assert child_prompt.seen[0] is not None
    assert child_prompt.seen[0].extras is extras


async def test_subagent_uses_the_parent_core_type(monkeypatch: Any):
    """A proxied parent must not hand its subagent the direct-provider core."""
    spawned: list[AgentCore] = []

    class ProxiedCore(AgentCore):
        def _spawn(self, agent_id: str, path: tuple[str, ...], tool_timeout: float, extras: dict[str, Any]) -> AgentCore:
            child = ProxiedCore(agent_id=agent_id, path=path, tool_timeout=tool_timeout, extras=extras)
            spawned.append(child)
            return child

        async def chat(self, provider: Any, messages: Any, prompts: Any = (), tools: Any = ()):
            return [AssistantMessage('child result')], None

    parent = ProxiedCore()
    tool = SubAgent([], [])
    provider = Provider('model', 'http://test', 0, 'key')
    result = await tool.run(ctx=ToolContext(core=parent, provider=provider, extras={}), prompt='go')

    assert result == 'child result'
    assert len(spawned) == 1
    assert type(spawned[0]) is ProxiedCore
