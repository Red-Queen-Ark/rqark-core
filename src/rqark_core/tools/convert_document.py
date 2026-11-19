import asyncio
from functools import cache
from pathlib import Path
from typing import Any

from rqark_core.types.tool import BaseTool, ToolContext

SUPPORTED_SUFFIXES: frozenset[str] = frozenset({'.docx', '.pdf'})


@cache
def _import_markitdown() -> Any:
    try:
        from markitdown import MarkItDown
    except ImportError:
        return None
    return MarkItDown


class ConvertDocument(BaseTool):
    @property
    def name(self) -> str:
        return 'convert_document'

    @property
    def display_key(self) -> str:
        return 'path'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Convert a Word (DOCX) or PDF document to Markdown. Writes a .md file next to the original and returns its path.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {'type': 'string', 'description': 'Path to the DOCX or PDF file'},
                        'output': {'type': 'string', 'description': 'Optional output path for the .md file. Defaults to the original path with a .md suffix'},
                    },
                    'required': ['path'],
                },
            },
        }

    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._convert, str(kwargs['path']), kwargs.get('output'))

    def _convert(self, path: str, output: str | None) -> str:
        src = Path(path)
        if not src.exists():
            return f'Error: file not found: {path}'
        if not src.is_file():
            return f'Error: not a file: {path}'
        if src.suffix.lower() not in SUPPORTED_SUFFIXES:
            return f'Error: unsupported file type: {src.suffix or "(none)"}. Only .docx and .pdf are supported'
        markitdown = _import_markitdown()
        if markitdown is None:
            return 'Error: markitdown is not installed'
        dest = Path(output) if output else src.with_suffix('.md')
        try:
            result = markitdown().convert(str(src))
        except Exception as e:
            return f'Error: failed to convert {path}: {e}'
        try:
            dest.write_text(result.markdown, encoding='utf-8')
        except OSError as e:
            return f'Error: cannot write {dest}: {e}'
        return f'Converted to {dest}'
