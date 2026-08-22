import subprocess
from pathlib import Path

from rqark_core.types.prompt import BasePrompt


class GitProjectPrompt(BasePrompt):
    """Gathers git project context: branch, status, recent commits."""

    priority = 70

    def __init__(self, cwd: Path | None = None):
        self.cwd = cwd or Path.cwd()

    @staticmethod
    def _run(cmd: list[str], cwd: Path) -> str | None:
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except Exception:
            return None

    def get_messages(self) -> str | None:
        # Check we're inside a git repo
        if not (self.cwd / '.git').exists():
            return None

        parts: list[str] = ['## Git Project Context']

        # Current branch
        branch = self._run(['git', 'branch', '--show-current'], self.cwd)
        if branch:
            parts.append(f'Current branch: {branch}')

        # Current HEAD commit
        head = self._run(['git', 'rev-parse', 'HEAD'], self.cwd)
        if head:
            parts.append(f'HEAD: {head}')

        # Status summary
        status = self._run(['git', 'status', '--porcelain'], self.cwd)
        if status:
            status_lines = status.split('\n')
            # Limit to 40 lines to avoid flooding the prompt
            parts.append('Working tree status (porcelain):\n' + '\n'.join(status_lines[:40]))
            if len(status_lines) > 40:
                parts.append(f'... ({len(status_lines) - 40} more lines truncated)')
        else:
            parts.append('Working tree: clean')

        # Recent commits
        log = self._run(['git', 'log', '--oneline', '-10', '--decorate'], self.cwd)
        if log:
            parts.append(f'Recent commits:\n{log}')

        return '\n\n'.join(parts)
