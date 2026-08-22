import asyncio
import re
from pathlib import Path
from typing import Any

from rqark_core.types.tool import BaseTool

SKIP_DIRS: tuple[str, ...] = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.idea', '.vscode')

MB: int = 1_000_000


class Grep(BaseTool):
    MAX_MATCHES: int = 200
    MAX_FILE_SIZE: int = MB
    catalog_group: str = 'read'

    @property
    def name(self) -> str:
        return 'grep'

    @property
    def display_key(self) -> str:
        return 'pattern'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Search file contents for a regular expression. Returns matching lines as path:line_number: content. Optionally restrict to files matching a glob include pattern.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'pattern': {'type': 'string', 'description': 'Regular expression to search for'},
                        'path': {'type': 'string', 'description': 'File or directory to search (defaults to current directory)'},
                        'include': {'type': 'string', 'description': 'Glob pattern to filter files, e.g. *.py'},
                    },
                    'required': ['pattern'],
                },
            },
        }

    async def run(self, **kwargs: Any) -> str:
        pattern = str(kwargs['pattern'])
        path = str(kwargs.get('path') or '.')
        include = kwargs.get('include')
        return await asyncio.to_thread(self._grep, pattern, path, str(include) if include else None)

    def _grep(self, pattern: str, path: str, include: str | None) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f'Error: invalid regex: {e}'
        root = Path(path)
        if not root.exists():
            return f'Error: path not found: {path}'
        if root.is_file():
            matches = self._search_file(root, regex)
        else:
            matches: list[str] = []
            self._walk_and_search(root, include or '*', regex, matches)
        if not matches:
            return f'No matches for: {pattern}'
        return '\n'.join(matches)

    def _walk_and_search(self, directory: Path, glob: str, regex: re.Pattern[str], matches: list[str]) -> bool:
        try:
            entries = sorted(directory.iterdir(), key=lambda e: e.name)
        except OSError:
            return False
        for entry in entries:
            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    continue
                if self._walk_and_search(entry, glob, regex, matches):
                    return True
            elif entry.match(glob):
                if entry.stat().st_size > self.MAX_FILE_SIZE:
                    continue
                result = self._search_file(entry, regex)
                if not result:
                    continue
                remaining = self.MAX_MATCHES - len(matches)
                if len(result) > remaining:
                    matches.extend(result[:remaining])
                    matches.append(f'... (truncated at {self.MAX_MATCHES} matches)')
                    return True
                matches.extend(result)
                if len(matches) >= self.MAX_MATCHES:
                    matches.append(f'... (truncated at {self.MAX_MATCHES} matches)')
                    return True
        return False

    def _search_file(self, file: Path, regex: re.Pattern[str]) -> list[str]:
        try:
            text = file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            return []
        results: list[str] = []
        for lineno, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                results.append(f'{file}:{lineno}: {line.strip()}')
        return results
