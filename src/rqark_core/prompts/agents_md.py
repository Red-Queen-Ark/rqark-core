from pathlib import Path

from rqark_core.types.prompt import BasePrompt, PromptContext


class AgentsMdPrompt(BasePrompt):
    priority = 50

    def __init__(self, cwd: Path | None = None):
        self.cwd = cwd or Path.cwd()

    async def get_messages(self, ctx: PromptContext | None = None) -> str | None:
        agents_md = self.cwd / 'AGENTS.md'
        if not agents_md.exists():
            return None
        content = agents_md.read_text(encoding='utf-8').strip()
        return f'## Project Instructions (AGENTS.md)\n\n{content}'
