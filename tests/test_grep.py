
import pytest

from rqark_core.libs.gitignore import GitIgnore
from rqark_core.tools.grep import Grep


def _write(path, text=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


@pytest.mark.parametrize(
    ('pattern', 'rel', 'is_dir', 'expected'),
    [
        ('*.log', 'a.log', False, True),
        ('*.log', 'deep/nested/a.log', False, True),
        ('*.log', 'a.txt', False, False),
        ('build', 'build', True, True),
        ('build', 'x/build', True, True),
        ('build/', 'build', True, True),
        ('build/', 'build', False, False),
        ('/top.txt', 'top.txt', False, True),
        ('/top.txt', 'sub/top.txt', False, False),
        ('src/*.py', 'src/a.py', False, True),
        ('src/*.py', 'src/sub/a.py', False, False),
        ('docs/**', 'docs/a/b.md', False, True),
        ('a/**/z.txt', 'a/z.txt', False, True),
        ('a/**/z.txt', 'a/b/c/z.txt', False, True),
        ('a/**/z.txt', 'other/z.txt', False, False),
        ('temp?.txt', 'temp1.txt', False, True),
        ('temp?.txt', 'temp12.txt', False, False),
        ('[ab].txt', 'a.txt', False, True),
        ('[!ab].txt', 'c.txt', False, True),
        ('[!ab].txt', 'a.txt', False, False),
    ],
)
def test_pattern_semantics(tmp_path, pattern, rel, is_dir, expected):
    _write(tmp_path / '.gitignore', pattern + '\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored(rel, is_dir) is expected


def test_negation_and_last_match_wins(tmp_path):
    _write(tmp_path / '.gitignore', '*.log\n!keep.log\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('drop.log', False) is True
    assert ignore.is_ignored('keep.log', False) is False


def test_comments_and_escaped_hash_are_not_patterns(tmp_path):
    _write(tmp_path / '.gitignore', '# comment\n\\#literal\n\n   \n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('comment', False) is False
    assert ignore.is_ignored('#literal', False) is True


def test_nested_gitignore_overrides_parent(tmp_path):
    _write(tmp_path / '.gitignore', '*.txt\n')
    _write(tmp_path / 'sub' / '.gitignore', '!keep.txt\n')
    (tmp_path / 'sub' / 'x.txt').write_text('x', encoding='utf-8')
    (tmp_path / 'sub' / 'keep.txt').write_text('k', encoding='utf-8')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('sub/x.txt', False) is True
    assert ignore.is_ignored('sub/keep.txt', False) is False
    assert ignore.is_ignored('other.txt', False) is True


def test_ignored_directory_covers_children(tmp_path):
    _write(tmp_path / '.gitignore', '.temp/\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('.temp', True) is True
    assert ignore.is_ignored('.temp/compare/compare.ipynb', False) is True


def test_parent_gitignore_of_git_root_applies(tmp_path):
    _write(tmp_path / '.gitignore', 'src/generated.py\n')
    (tmp_path / '.git').mkdir()
    _write(tmp_path / 'src' / 'generated.py', 'x')
    ignore = GitIgnore.load(tmp_path / 'src')
    assert ignore.is_ignored('generated.py', False) is True


def test_git_info_exclude_applies(tmp_path):
    (tmp_path / '.git' / 'info').mkdir(parents=True)
    _write(tmp_path / '.git' / 'info' / 'exclude', 'secret.txt\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('secret.txt', False) is True


def test_gitignore_inside_skipped_dir_is_not_scanned(tmp_path):
    _write(tmp_path / '.venv' / '.gitignore', 'a.txt\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('a.txt', False) is False


async def test_grep_skips_ignored_files(tmp_path):
    _write(tmp_path / '.gitignore', '.temp/\n')
    _write(tmp_path / '.temp' / 'compare' / 'compare.ipynb', 'otp_enabled\n')
    _write(tmp_path / 'src' / 'app.py', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path))
    assert 'app.py' in result
    assert 'compare.ipynb' not in result


async def test_grep_include_ignored_searches_everything(tmp_path):
    _write(tmp_path / '.gitignore', '.temp/\n')
    _write(tmp_path / '.temp' / 'compare' / 'compare.ipynb', 'otp_enabled\n')
    _write(tmp_path / 'src' / 'app.py', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path), include_ignored=True)
    assert 'app.py' in result
    assert 'compare.ipynb' in result


async def test_grep_explicit_ignored_file_is_still_searched(tmp_path):
    _write(tmp_path / '.gitignore', 'secret.txt\n')
    _write(tmp_path / 'secret.txt', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path / 'secret.txt'))
    assert 'secret.txt' in result
    assert 'No matches' not in result


async def test_grep_still_skips_hardcoded_dirs(tmp_path):
    _write(tmp_path / 'node_modules' / 'pkg' / 'index.js', 'otp_enabled\n')
    _write(tmp_path / 'src' / 'app.py', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path))
    assert 'app.py' in result
    assert 'node_modules' not in result


async def test_grep_default_path_relative_root(tmp_path, monkeypatch):
    _write(tmp_path / '.gitignore', '.temp/\n')
    _write(tmp_path / '.temp' / 'x.txt', 'otp_enabled\n')
    _write(tmp_path / 'app.py', 'otp_enabled\n')
    monkeypatch.chdir(tmp_path)
    result = await Grep().run(pattern='otp')
    assert 'app.py' in result
    assert '.temp' not in result


async def test_grep_include_glob_still_works(tmp_path):
    _write(tmp_path / '.gitignore', '*.log\n')
    _write(tmp_path / 'a.py', 'otp_enabled\n')
    _write(tmp_path / 'b.log', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path), include='*.log')
    assert 'b.log' not in result
    assert 'No matches' in result
