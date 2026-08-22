import asyncio
from pathlib import Path
from typing import Any

from rqark_core.types.tool import BaseTool

SKIP_DIRS: tuple[str, ...] = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.idea', '.vscode')


class ListDir(BaseTool):

    @property
    def name(self) -> str:
        return 'list_dir'

    @property
    def display_key(self) -> str:
        return 'path'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'List the entries of a directory. Subdirectories are suffixed with a trailing slash.',
                'parameters': {'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Directory path to list (defaults to current directory)'}}, 'required': []},
            },
        }

    async def run(self, **kwargs: Any) -> str:
        path = str(kwargs.get('path') or '.')
        return await asyncio.to_thread(self._list, path)

    def _list(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            return f'Error: path not found: {path}'
        if not p.is_dir():
            return f'Error: not a directory: {path}'
        try:
            entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except OSError as e:
            return f'Error: cannot list directory: {e}'
        entries = [e for e in entries if e.name not in SKIP_DIRS]
        if not entries:
            return f'(empty directory: {path})'
        lines = [f'{e.name}/' if e.is_dir() else e.name for e in entries]
        return '\n'.join(lines)
