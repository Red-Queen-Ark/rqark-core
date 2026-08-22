import asyncio
from pathlib import Path
from typing import Any

from rqark_core.types.tool import BaseTool


class WriteFile(BaseTool):

    @property
    def name(self) -> str:
        return 'write_file'

    @property
    def display_key(self) -> str:
        return 'path'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Write text content to a file, overwriting any existing content. Parent directories are created automatically. For targeted edits use edit_file instead.',
                'parameters': {
                    'type': 'object',
                    'properties': {'path': {'type': 'string', 'description': 'Path to the file to write'}, 'content': {'type': 'string', 'description': 'The full text content to write'}},
                    'required': ['path', 'content'],
                },
            },
        }

    async def run(self, **kwargs: Any) -> str:
        path = str(kwargs['path'])
        content = str(kwargs['content'])
        return await asyncio.to_thread(self._write, path, content)

    def _write(self, path: str, content: str) -> str:
        p = Path(path)
        try:
            if p.parent and not p.parent.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
        except OSError as e:
            return f'Error: cannot write file: {e}'
        return f'Wrote {len(content)} chars to {path}'
