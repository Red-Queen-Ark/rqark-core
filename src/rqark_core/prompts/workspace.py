from pathlib import Path

from rqark_core.types.prompt import BasePrompt


class WorkspacePrompt(BasePrompt):
    priority = 40

    def __init__(self, cwd: Path | None = None):
        self.cwd = cwd or Path.cwd()

    def get_messages(self) -> str:
        return f'## Workspace\nCurrent workspace: {self.cwd}'
