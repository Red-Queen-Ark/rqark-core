import asyncio
import subprocess
import sys
from pathlib import Path

from rqark_core.types.prompt import BasePrompt, PromptContext


def _creation_flags() -> int:
    if sys.platform != 'win32':
        return 0
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class GitProjectPrompt(BasePrompt):
    """The repository state of the working directory: branch, HEAD, status and recent commits.

    The four commands run through ``git``, so they are run in worker threads and
    together: a slow repository (network share, on-access virus scan) must not hold
    the event loop, and the prompts of a turn are awaited while the UI is running.
    """

    priority = 70

    def __init__(self, cwd: Path | None = None):
        self.cwd = cwd or Path.cwd()

    @staticmethod
    def _run(cmd: list[str], cwd: Path) -> str | None:
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10, creationflags=_creation_flags())
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except Exception:
            return None

    async def _run_all(self, *commands: list[str]) -> list[str | None]:
        return await asyncio.gather(*(asyncio.to_thread(self._run, cmd, self.cwd) for cmd in commands))

    async def get_messages(self, ctx: PromptContext | None = None) -> str | None:
        if not (self.cwd / '.git').exists():
            return None

        branch, head, status, log = await self._run_all(
            ['git', 'branch', '--show-current'],
            ['git', 'rev-parse', 'HEAD'],
            ['git', 'status', '--porcelain'],
            ['git', 'log', '--oneline', '-10', '--decorate'],
        )

        parts: list[str] = ['## Git Project Context']
        if branch:
            parts.append(f'Current branch: {branch}')
        if head:
            parts.append(f'HEAD: {head}')
        if status:
            status_lines = status.split('\n')
            parts.append('Working tree status (porcelain):\n' + '\n'.join(status_lines[:40]))
            if len(status_lines) > 40:
                parts.append(f'... ({len(status_lines) - 40} more lines truncated)')
        else:
            parts.append('Working tree: clean')
        if log:
            parts.append(f'Recent commits:\n{log}')

        return '\n\n'.join(parts)
