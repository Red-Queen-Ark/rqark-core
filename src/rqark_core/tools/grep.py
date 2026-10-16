import asyncio
import re
from pathlib import Path
from typing import Any

from rqark_core.libs.gitignore import GitIgnore
from rqark_core.types.tool import BaseTool, ToolContext

SKIP_DIRS: tuple[str, ...] = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.idea', '.vscode')

MB: int = 1_000_000


class Grep(BaseTool):
    MAX_MATCHES: int = 200
    MAX_FILE_SIZE: int = MB

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
                'description': 'Search file contents for a regular expression. Returns matching lines as path:line_number: content. Optionally restrict to files matching a glob include pattern. Files excluded by .gitignore are skipped when searching a directory; an explicitly given file path is always searched.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'pattern': {'type': 'string', 'description': 'Regular expression to search for'},
                        'path': {'type': 'string', 'description': 'File or directory to search (defaults to current directory)'},
                        'include': {'type': 'string', 'description': 'Glob pattern to filter files, e.g. *.py'},
                        'include_ignored': {'type': 'boolean', 'description': 'Also search files excluded by .gitignore (defaults to false)'},
                    },
                    'required': ['pattern'],
                },
            },
        }

    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str:
        pattern = str(kwargs['pattern'])
        path = str(kwargs.get('path') or '.')
        include = kwargs.get('include')
        include_ignored = bool(kwargs.get('include_ignored'))
        return await asyncio.to_thread(self._grep, pattern, path, str(include) if include else None, include_ignored)

    def _grep(self, pattern: str, path: str, include: str | None, include_ignored: bool) -> str:
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
            matches = []
            ignore = None if include_ignored else GitIgnore.load(root)
            self._walk_and_search(root, root, include or '*', regex, matches, ignore)
        if not matches:
            return f'No matches for: {pattern}'
        return '\n'.join(matches)

    def _walk_and_search(self, root: Path, directory: Path, glob: str, regex: re.Pattern[str], matches: list[str], ignore: GitIgnore | None) -> bool:
        try:
            entries = sorted(directory.iterdir(), key=lambda e: e.name)
        except OSError:
            return False
        for entry in entries:
            rel = entry.relative_to(root).as_posix()
            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    continue
                if ignore is not None and ignore.is_ignored(rel, True):
                    continue
                if self._walk_and_search(root, entry, glob, regex, matches, ignore):
                    return True
            elif entry.match(glob):
                if ignore is not None and ignore.is_ignored(rel, False):
                    continue
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
        except UnicodeDecodeError, OSError:
            return []
        results: list[str] = []
        for lineno, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                results.append(f'{file}:{lineno}: {line.strip()}')
        return results
