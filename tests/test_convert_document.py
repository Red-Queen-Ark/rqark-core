from pathlib import Path
from typing import Any

import pytest

from rqark_core.tools import convert_document
from rqark_core.tools.convert_document import ConvertDocument


class _Result:
    markdown = '# hello'


class _FakeMarkItDown:
    def convert(self, path: str) -> _Result:
        return _Result()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(convert_document, 'MarkItDown', _FakeMarkItDown)


async def test_converts_docx_next_to_original(tmp_path: Path, fake: None) -> None:
    src = tmp_path / 'a.docx'
    src.write_bytes(b'x')
    result = await ConvertDocument().run(path=str(src))
    out = tmp_path / 'a.md'
    assert out.read_text(encoding='utf-8') == '# hello'
    assert str(out) in result


async def test_custom_output(tmp_path: Path, fake: None) -> None:
    src = tmp_path / 'a.pdf'
    src.write_bytes(b'x')
    out = tmp_path / 'out.md'
    await ConvertDocument().run(path=str(src), output=str(out))
    assert out.read_text(encoding='utf-8') == '# hello'


async def test_rejects_unsupported(tmp_path: Path, fake: None) -> None:
    src = tmp_path / 'a.txt'
    src.write_text('x', encoding='utf-8')
    assert 'unsupported' in await ConvertDocument().run(path=str(src))


async def test_missing_markitdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / 'a.pdf'
    src.write_bytes(b'x')
    monkeypatch.setattr(convert_document, 'MarkItDown', None)
    assert 'markitdown is not installed' in await ConvertDocument().run(path=str(src))


def test_schema() -> None:
    schema: dict[str, Any] = ConvertDocument().get_openai_schema()
    assert schema['function']['name'] == 'convert_document'
