import re
from dataclasses import dataclass
from pathlib import Path


def _strip_trailing_spaces(line: str) -> str:
    end = len(line)
    while end > 0 and line[end - 1] == ' ' and (end < 2 or line[end - 2] != '\\'):
        end -= 1
    return line[:end]


def _translate(body: str) -> str:
    out: list[str] = []
    i = 0
    size = len(body)
    while i < size:
        char = body[i]
        if char == '*':
            if body[i : i + 2] == '**':
                segment_start = i == 0 or body[i - 1] == '/'
                after = i + 2
                if segment_start and body[after : after + 1] == '/':
                    out.append('(?:.*/)?')
                    i = after + 1
                elif segment_start and after == size:
                    out.append('.*')
                    i = after
                else:
                    out.append('[^/]*')
                    i += 1
            else:
                out.append('[^/]*')
                i += 1
        elif char == '?':
            out.append('[^/]')
            i += 1
        elif char == '[':
            close = i + 1
            if close < size and body[close] in '!^':
                close += 1
            if close < size and body[close] == ']':
                close += 1
            while close < size and body[close] != ']':
                close += 1
            if close >= size:
                out.append(re.escape('['))
                i += 1
            else:
                inner = body[i + 1 : close]
                if inner.startswith('!'):
                    inner = '^' + inner[1:]
                out.append(f'[{inner}]')
                i = close + 1
        elif char == '\\' and i + 1 < size:
            out.append(re.escape(body[i + 1]))
            i += 2
        else:
            out.append(re.escape(char))
            i += 1
    return ''.join(out)


@dataclass(frozen=True)
class _Rule:
    base: str
    regex: re.Pattern[str]
    negated: bool
    dir_only: bool

    def match(self, absolute: str, is_dir: bool) -> bool | None:
        if not absolute.startswith(self.base):
            return None
        if self.dir_only and not is_dir:
            return None
        if self.regex.match(absolute[len(self.base) :]) is None:
            return None
        return not self.negated


def _parse_line(line: str, base: str) -> _Rule | None:
    line = _strip_trailing_spaces(line.rstrip('\r'))
    if not line.strip():
        return None
    if line.startswith('#'):
        return None
    negated = line.startswith('!')
    if negated:
        line = line[1:]
    elif line.startswith(('\\#', '\\!')):
        line = line[1:]
    dir_only = line.endswith('/')
    body = line.strip('/')
    if not body:
        return None
    anchored = line.startswith('/') or '/' in body
    translated = _translate(body)
    prefix = '^' if anchored else '^(?:.*/)?'
    return _Rule(base=base, regex=re.compile(prefix + translated + '$'), negated=negated, dir_only=dir_only)


def _read_rules(gitignore: Path, base: str) -> list[_Rule]:
    try:
        text = gitignore.read_text(encoding='utf-8')
    except OSError, UnicodeDecodeError:
        return []
    rules: list[_Rule] = []
    for line in text.splitlines():
        rule = _parse_line(line, base)
        if rule is not None:
            rules.append(rule)
    return rules


def _find_git_dir(start: Path) -> Path | None:
    current = start
    while True:
        candidate = current / '.git'
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


class GitIgnore:
    def __init__(self, root: str, rules: list[_Rule]) -> None:
        self._root = root
        self._rules = rules
        self._loaded: set[str] = {''}

    @classmethod
    def load(cls, root: Path) -> 'GitIgnore':
        resolved = root.resolve()
        rules: list[_Rule] = []
        git_dir = _find_git_dir(resolved)
        if git_dir is None:
            rules.extend(_read_rules(resolved / '.gitignore', str(resolved) + '/'))
        else:
            rules.extend(_read_rules(git_dir / 'info' / 'exclude', str(git_dir.parent) + '/'))
            chain: list[Path] = []
            current = resolved
            while current.parent != current:
                chain.append(current)
                if current == git_dir.parent:
                    break
                current = current.parent
            for directory in reversed(chain):
                rules.extend(_read_rules(directory / '.gitignore', str(directory) + '/'))
        return cls(root=str(resolved), rules=rules)

    def _ensure(self, rel: str) -> None:
        if rel in self._loaded:
            return
        self._loaded.add(rel)
        base = f'{self._root}/' if not rel else f'{self._root}/{rel}/'
        self._rules.extend(_read_rules(Path(base) / '.gitignore', base))

    def _decide(self, absolute: str, is_dir: bool) -> bool:
        ignored = False
        for rule in self._rules:
            matched = rule.match(absolute, is_dir)
            if matched is not None:
                ignored = matched
        return ignored

    def is_ignored(self, rel: str, is_dir: bool) -> bool:
        parts = rel.split('/')
        last = len(parts) if is_dir else len(parts) - 1
        for depth in range(0, last + 1):
            self._ensure('/'.join(parts[:depth]))
        for depth in range(1, last + 1):
            if self._decide(f'{self._root}/' + '/'.join(parts[:depth]), True):
                return True
        return self._decide(f'{self._root}/' + rel, is_dir)
