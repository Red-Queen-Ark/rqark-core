import sys

import pytest

from rqark_core.tools.exec import Exec, _decode_output

_UTF16LE_WSL_STYLE = '  NAME            STATE           VERSION\n'.encode('utf-16-le')
_UTF16_BOM = b'\xff\xfe' + '  NAME'.encode('utf-16-le')


@pytest.mark.parametrize('data', [_UTF16LE_WSL_STYLE, _UTF16_BOM, b'\x00abc', b'abc\x00', b'\x00\x00\x00\x00\xff', b'\xff\xfe\x41', 'str\x00input', None])
def test_nul_never_survives_decoding(data):
    assert '\x00' not in _decode_output(data)


def test_utf16le_without_bom_is_decoded():
    assert _decode_output(_UTF16LE_WSL_STYLE) == '  NAME            STATE           VERSION\n'


def test_utf16_with_bom_is_decoded():
    assert _decode_output(_UTF16_BOM) == '  NAME'


def test_utf8_is_passed_through_unchanged():
    assert _decode_output('中文 ok'.encode()) == '中文 ok'


def test_invalid_bytes_fall_back_to_replacement_characters():
    assert _decode_output('中文'.encode('cp950')) == '\ufffd' * 4


def test_odd_length_utf16_candidate_falls_back_to_utf8():
    assert _decode_output(b'\x00\x00\x00\x00\xff') == '\ufffd'


def test_none_and_empty_decode_to_empty_string():
    assert _decode_output(None) == ''
    assert _decode_output(b'') == ''


def test_utf8_nul_bytes_are_stripped():
    assert _decode_output(b'a\x00b') == 'ab'


async def test_exec_tool_strips_nul_from_utf16_subprocess_output(tmp_path):
    script = tmp_path / 'emit_utf16.py'
    script.write_text("import sys\nsys.stdout.buffer.write('  NAME'.encode('utf-16-le'))\n", encoding='utf-8')
    result = await Exec().run(command=f'{sys.executable} {script}')
    assert '\x00' not in result
    assert 'exit code: 0' in result
    assert '  NAME' in result
