import asyncio
import fnmatch
import os
import re
import threading
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from rqark_core.libs.gitignore import GitIgnore
from rqark_core.types.tool import BaseTool, ToolContext

SKIP_DIRS: tuple[str, ...] = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.idea', '.vscode')

MB: int = 1_000_000

_PURE = PureWindowsPath if os.name == 'nt' else PurePosixPath


class _Glob:
    def __init__(self, glob: str) -> None:
        self._glob = os.path.normcase(glob)
        self._path_glob = '/' in glob

    def matches(self, rel: str, name: str) -> bool:
        target = os.path.normcase(rel if self._path_glob else name)
        try:
            return _PURE(target).match(self._glob)
        except ValueError:
            return fnmatch.fnmatchcase(target, self._glob)


class Grep(BaseTool):
    MAX_MATCHES: int = 200
    MAX_FILE_SIZE: int = MB
    MAX_DEPTH: int = 24
    MAX_FILES: int = 20_000
    TIMEOUT: float = 30.0

    @property
    def name(self) -> str:
        return 'grep'

    @property
    def display_key(self) -> str:
        return 'pattern'

    @property
    def timeout(self) -> float | None:
        return self.TIMEOUT

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
        cancel = threading.Event()
        worker = asyncio.ensure_future(asyncio.to_thread(self._grep, pattern, path, str(include) if include else None, include_ignored, cancel))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancel.set()
            worker.add_done_callback(self._consume)
            raise

    @staticmethod
    def _consume(task: asyncio.Future) -> None:
        if not task.cancelled():
            task.exception()

    def _grep(self, pattern: str, path: str, include: str | None, include_ignored: bool, cancel: threading.Event | None = None) -> str:
        if cancel is None:
            cancel = threading.Event()
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f'Error: invalid regex: {e}'
        root = Path(path)
        if not root.exists():
            return f'Error: path not found: {path}'
        if root.is_file():
            matches = [] if self._too_large(root) else self._search_file(root, regex)
            if not matches:
                return f'No matches for: {pattern}'
            return '\n'.join(matches)
        matches = []
        ignore = None if include_ignored else GitIgnore.load(root)
        truncated = self._walk(root, _Glob(include or '*'), regex, matches, ignore, cancel)
        if not matches:
            return f'No matches for: {pattern}'
        if truncated:
            matches.append(f'... (truncated at {self.MAX_MATCHES} matches)')
        return '\n'.join(matches)

    def _walk(self, root: Path, glob: _Glob, regex: re.Pattern[str], matches: list[str], ignore: GitIgnore | None, cancel: threading.Event) -> bool:
        stack: list[tuple[Path, str, int]] = [(root, '', 0)]
        seen: set[tuple[int, int]] = set()
        files = 0
        while stack:
            if cancel.is_set():
                return False
            directory, rel_dir, depth = stack.pop()
            key = self._inode(directory)
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            try:
                with os.scandir(directory) as scan:
                    entries = sorted(scan, key=lambda e: e.name)
            except OSError:
                continue
            subdirs: list[tuple[Path, str, int]] = []
            for entry in entries:
                if cancel.is_set():
                    return False
                rel = f'{rel_dir}/{entry.name}' if rel_dir else entry.name
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if is_dir:
                    if entry.name in SKIP_DIRS:
                        continue
                    if ignore is not None and ignore.is_ignored(rel, True):
                        continue
                    if depth + 1 > self.MAX_DEPTH:
                        continue
                    subdirs.append((Path(entry.path), rel, depth + 1))
                    continue
                if not glob.matches(rel, entry.name):
                    continue
                if ignore is not None and ignore.is_ignored(rel, False):
                    continue
                files += 1
                if files > self.MAX_FILES:
                    return True
                try:
                    if entry.stat(follow_symlinks=False).st_size > self.MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                result = self._search_file(Path(entry.path), regex)
                if not result:
                    continue
                remaining = self.MAX_MATCHES - len(matches)
                if len(result) > remaining:
                    matches.extend(result[:remaining])
                    return True
                matches.extend(result)
                if len(matches) >= self.MAX_MATCHES:
                    return True
            stack.extend(reversed(subdirs))
        return False

    @staticmethod
    def _inode(path: Path) -> tuple[int, int] | None:
        try:
            st = os.stat(path, follow_symlinks=False)
        except OSError:
            return None
        return (st.st_dev, st.st_ino)

    def _too_large(self, file: Path) -> bool:
        try:
            return os.stat(file, follow_symlinks=False).st_size > self.MAX_FILE_SIZE
        except OSError:
            return True

    def _search_file(self, file: Path, regex: re.Pattern[str]) -> list[str]:
        results: list[str] = []
        try:
            with file.open('r', encoding='utf-8') as handle:
                for lineno, line in enumerate(handle, 1):
                    if regex.search(line):
                        results.append(f'{file}:{lineno}: {line.strip()}')
        except (UnicodeDecodeError, OSError):
            return []
        return results
