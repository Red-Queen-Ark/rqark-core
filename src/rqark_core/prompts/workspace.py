from pathlib import Path

from rqark_core.types.prompt import BasePrompt, PromptContext


class WorkspacePrompt(BasePrompt):
    priority = 40

    def __init__(self, cwd: Path | None = None):
        self.cwd = cwd or Path.cwd()

    async def get_messages(self, ctx: PromptContext | None = None) -> str:
        return f'## Workspace\nCurrent workspace: {self.cwd}'
