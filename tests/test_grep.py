import threading

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
    assert ignore.is_ignored('keep.log', False) is False
    assert ignore.is_ignored('drop.log', False) is True


def test_comments_and_escaped_hash_are_not_patterns(tmp_path):
    _write(tmp_path / '.gitignore', '# comment\n\\#literal\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('# comment', False) is False
    assert ignore.is_ignored('#literal', False) is True


def test_nested_gitignore_overrides_parent(tmp_path):
    _write(tmp_path / '.gitignore', '*.log\n')
    _write(tmp_path / 'sub' / '.gitignore', '!keep.log\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('sub/keep.log', False) is False
    assert ignore.is_ignored('keep.log', False) is True


def test_ignored_directory_covers_children(tmp_path):
    _write(tmp_path / '.gitignore', 'build/\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('build', True) is True
    assert ignore.is_ignored('build/out.o', False) is True


def test_parent_gitignore_of_git_root_applies(tmp_path):
    (tmp_path / '.git').mkdir()
    _write(tmp_path / '.gitignore', '*.log\n')
    _write(tmp_path / 'sub' / '.gitignore', '!keep.log\n')
    ignore = GitIgnore.load(tmp_path / 'sub')
    assert ignore.is_ignored('drop.log', False) is True
    assert ignore.is_ignored('keep.log', False) is False


def test_git_info_exclude_applies(tmp_path):
    _write(tmp_path / '.git' / 'info' / 'exclude', '*.log\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('a.log', False) is True


def test_gitignore_inside_skipped_dir_is_not_scanned(tmp_path):
    _write(tmp_path / '.gitignore', 'build/\n')
    _write(tmp_path / 'build' / '.gitignore', '!keep.log\n')
    ignore = GitIgnore.load(tmp_path)
    assert ignore.is_ignored('build/keep.log', False) is True


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


async def test_grep_does_not_follow_symlink_cycle(tmp_path):
    _write(tmp_path / 'a' / 'deep' / 'app.py', 'otp_enabled\n')
    (tmp_path / 'a' / 'loop').symlink_to(tmp_path)
    result = await Grep().run(pattern='otp', path=str(tmp_path))
    assert 'app.py' in result


async def test_grep_respects_max_depth(tmp_path, monkeypatch):
    monkeypatch.setattr(Grep, 'MAX_DEPTH', 1)
    _write(tmp_path / 'one' / 'two' / 'three' / 'deep.txt', 'otp_enabled\n')
    _write(tmp_path / 'top.txt', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path))
    assert 'top.txt' in result
    assert 'deep.txt' not in result


async def test_grep_respects_max_files(tmp_path, monkeypatch):
    monkeypatch.setattr(Grep, 'MAX_FILES', 1)
    _write(tmp_path / 'a.txt', 'otp_enabled\n')
    _write(tmp_path / 'b.txt', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path))
    assert 'truncated at' in result


async def test_grep_skips_files_over_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(Grep, 'MAX_FILE_SIZE', 4)
    _write(tmp_path / 'big.txt', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path))
    assert 'No matches' in result


async def test_grep_explicit_file_over_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(Grep, 'MAX_FILE_SIZE', 4)
    _write(tmp_path / 'big.txt', 'otp_enabled\n')
    result = await Grep().run(pattern='otp', path=str(tmp_path / 'big.txt'))
    assert 'No matches' in result


def test_grep_stops_when_cancelled(tmp_path):
    _write(tmp_path / 'a.txt', 'otp_enabled\n')
    cancel = threading.Event()
    cancel.set()
    result = Grep()._grep('otp', str(tmp_path), None, False, cancel)
    assert 'No matches' in result


def test_grep_exposes_a_timeout():
    assert Grep().timeout is not None
    assert Grep().timeout > 0
