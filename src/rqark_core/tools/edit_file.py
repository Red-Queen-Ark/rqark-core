import asyncio
import difflib
import os
import threading
from pathlib import Path
from typing import Any

from rqark_core.types.tool import BaseTool, ToolContext

_EDIT_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _path_lock(path: str) -> threading.Lock:
    key = os.path.normcase(str(Path(path).resolve()))
    with _LOCKS_GUARD:
        lock = _EDIT_LOCKS.get(key)
        if lock is None:
            lock = _EDIT_LOCKS[key] = threading.Lock()
        return lock


def _split_keep_blanks(text: str) -> list[str]:
    parts = text.split('\n')
    if parts and parts[-1] == '':
        parts = parts[:-1]
    return parts


def _find_best_match(target_lines: list[str], search_lines: list[str], min_ratio: float = 0.5) -> tuple[int, float]:
    window = len(search_lines)
    if window == 0 or window > len(target_lines):
        return -1, 0.0

    for i in range(len(target_lines) - window + 1):
        if target_lines[i : i + window] == search_lines:
            return i, 1.0

    stripped_target = [line.strip() for line in target_lines]
    stripped_search = [line.strip() for line in search_lines]
    for i in range(len(stripped_target) - window + 1):
        if stripped_target[i : i + window] == stripped_search:
            return i, 1.0

    best_ratio, best_pos = 0.0, -1
    for i in range(len(target_lines) - window + 1):
        ratio = difflib.SequenceMatcher(None, search_lines, target_lines[i : i + window]).ratio()
        if ratio > best_ratio:
            best_ratio, best_pos = ratio, i

    if best_ratio > min_ratio:
        return best_pos, best_ratio
    return -1, best_ratio


def _not_found_msg(target_lines: list[str], search_lines: list[str], path: str, best_pos: int = -1, best_ratio: float = 0.0) -> str:
    if best_ratio > 0.5 and best_pos >= 0:
        window = len(search_lines)
        diff = '\n'.join(difflib.unified_diff(search_lines, target_lines[best_pos : best_pos + window], fromfile='old_text (provided)', tofile=f'{path} (actual, line {best_pos + 1})', lineterm=''))
        return f'Error: old_text not found in {path}.\nBest match ({best_ratio:.0%} similar) at line {best_pos + 1}:\n{diff}'
    return f'Error: old_text not found in {path}. No similar text found. Verify the file content.'


def _find_substring_match(content: str, old_text: str) -> tuple[str | None, int]:
    if old_text in content:
        return old_text, content.count(old_text)

    old_lines = _split_keep_blanks(old_text)
    if not old_lines:
        return None, 0
    stripped_old = [line.strip() for line in old_lines]
    content_lines = _split_keep_blanks(content)

    candidates: list[str] = []
    for i in range(len(content_lines) - len(stripped_old) + 1):
        window = content_lines[i : i + len(stripped_old)]
        if [line.strip() for line in window] == stripped_old:
            candidates.append('\n'.join(window))

    if candidates:
        return candidates[0], len(candidates)
    return None, 0


def _edit_file_content(fp: Path, old_string: str, new_string: str, replace_all: bool = False) -> str:
    if not fp.exists():
        return f'Error: File not found: {fp}'
    if not fp.is_file():
        return f'Error: Not a regular file: {fp}'

    raw = fp.read_bytes()
    crlf_count = raw.count(b'\r\n')
    lf_count = raw.count(b'\n') - crlf_count
    use_crlf = crlf_count > lf_count

    content = raw.decode('utf-8').replace('\r\n', '\n')
    search_text = old_string.replace('\r\n', '\n')

    match, count = _find_substring_match(content, search_text)
    if match is None:
        lines = content.split('\n')
        search_lines = search_text.split('\n')
        pos, ratio = _find_best_match(lines, search_lines)
        return _not_found_msg(lines, search_lines, str(fp), best_pos=pos, best_ratio=ratio)

    if count > 1 and not replace_all:
        return f'Warning: old_text appears {count} times. Provide more context to make it unique, or set replace_all=true.'

    norm_new = new_string.replace('\r\n', '\n')
    new_content = content.replace(match, norm_new, 1 if not replace_all else count)
    if use_crlf:
        new_content = new_content.replace('\n', '\r\n')

    fp.write_bytes(new_content.encode('utf-8'))
    return f'Successfully edited {fp}'


class EditFile(BaseTool):
    @property
    def name(self) -> str:
        return 'edit_file'

    @property
    def display_key(self) -> str:
        return 'path'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': (
                    'Perform exact string replacements in a file. When editing text, ensure you preserve the exact indentation (tabs/spaces) as it appears before. Use replace_all to change every instance. Never run two edits on the same file in parallel — they race and one edit is lost.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {'type': 'string', 'description': 'The path to the file to modify.'},
                        'old_string': {'type': 'string', 'description': 'The text to replace. Must match exactly including whitespace.'},
                        'new_string': {'type': 'string', 'description': 'The text to replace it with (must be different from old_string).'},
                        'replace_all': {'type': 'boolean', 'description': 'Replace all occurrences of old_string (default false).'},
                    },
                    'required': ['path', 'old_string', 'new_string'],
                },
            },
        }

    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str:
        path = str(kwargs.get('path', ''))
        old_string = str(kwargs.get('old_string', ''))
        new_string = str(kwargs.get('new_string', ''))
        replace_all = bool(kwargs.get('replace_all', False))

        if not path:
            return 'Error: path is required'
        if not old_string:
            return 'Error: old_string is required'
        if new_string == old_string:
            return 'Error: new_string must be different from old_string'

        def _edit() -> str:
            with _path_lock(path):
                return _edit_file_content(Path(path), old_string, new_string, replace_all)

        return await asyncio.to_thread(_edit)
