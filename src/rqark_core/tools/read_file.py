import asyncio
from pathlib import Path
from typing import Any

from rqark_core.types.tool import BaseTool


class ReadFile(BaseTool):
    DEFAULT_LIMIT: int = 2000
    catalog_group: str = 'read'

    @property
    def name(self) -> str:
        return 'read_file'

    @property
    def display_key(self) -> str:
        return 'path'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Read the contents of a text file. Returns each line prefixed with its 1-indexed line number. Use offset/limit to read a slice of large files.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {'type': 'string', 'description': 'Path to the file to read'},
                        'offset': {'type': 'integer', 'description': 'Line number to start from (1-indexed)'},
                        'limit': {'type': 'integer', 'description': 'Maximum number of lines to read'},
                    },
                    'required': ['path'],
                },
            },
        }

    async def run(self, **kwargs: Any) -> str:
        path = str(kwargs['path'])
        offset = int(kwargs.get('offset') or 1)
        limit = int(kwargs.get('limit') or self.DEFAULT_LIMIT)
        return await asyncio.to_thread(self._read, path, offset, limit)

    def _read(self, path: str, offset: int, limit: int) -> str:
        p = Path(path)
        if not p.exists():
            return f'Error: file not found: {path}'
        if p.is_dir():
            return f'Error: path is a directory: {path}'
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return f'Error: cannot decode file as UTF-8: {path}'
        except OSError as e:
            return f'Error: cannot read file: {e}'
        lines = text.splitlines()
        start = max(offset, 1)
        selected = lines[start - 1 : start - 1 + limit]
        if not selected:
            return f'(no content at offset {offset})'
        numbered = [f'{start + i}: {line}' for i, line in enumerate(selected)]
        return '\n'.join(numbered)
