import asyncio
import os
import re
import shlex
import subprocess
import sys
from typing import Any

from rqark_core.types.tool import BaseTool

_MAX_COMMAND_LENGTH: int = 2000

_SHELL_METACHARS: re.Pattern[str] = re.compile(r'[|;&$`()*?[\]~#!{}<>]')


def _needs_shell(command: str) -> bool:
    return bool(_SHELL_METACHARS.search(command))


def _format_output(stdout: str, stderr: str, returncode: int) -> str:
    max_len = 8000
    if len(stdout) > max_len:
        stdout = stdout[:max_len] + f'\n… (truncated, total {len(stdout)} chars)'
    if len(stderr) > max_len:
        stderr = stderr[:max_len] + f'\n… (truncated, total {len(stderr)} chars)'

    parts: list[str] = [f'exit code: {returncode}']
    if stdout:
        parts.append(f'stdout:\n{stdout}')
    if stderr:
        parts.append(f'stderr:\n{stderr}')
    if not stdout and not stderr:
        parts.append('(no output)')
    return '\n'.join(parts)


def _decode_output(data: bytes | str | None) -> str:
    return data.decode('utf-8', errors='replace') if isinstance(data, bytes) else data or ''


def _build_env() -> dict[str, str]:
    return {**os.environ, 'PYTHONUNBUFFERED': '1'}


def _spawn_kwargs(stdin: Any = subprocess.DEVNULL) -> dict[str, Any]:
    kw: dict[str, Any] = dict(stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if sys.platform == 'win32':
        kw['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    return kw


async def _kill_proc(proc: asyncio.subprocess.Process) -> None:
    if sys.platform == 'win32' and proc.pid:
        try:
            killer = await asyncio.create_subprocess_exec(
                'taskkill', '/F', '/T', '/PID', str(proc.pid),
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(killer.wait(), timeout=5)
        except (OSError, asyncio.TimeoutError, ProcessLookupError):
            pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except (asyncio.TimeoutError, ProcessLookupError):
        pass


class Exec(BaseTool):
    DEFAULT_TIMEOUT: int = 60
    catalog_group: str = 'write'

    @property
    def name(self) -> str:
        return 'exec'

    @property
    def display_key(self) -> str:
        return 'command'

    @property
    def aliases(self) -> tuple[str, ...]:
        return ('shell',)

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': (
                    'Execute a shell command in a subprocess. '
                    'Returns exit code, stdout, and stderr. '
                    'ONLY use this for CLI tools, scripts, git, build commands, linters, and package managers. '
                    'DO NOT use for reading files (use read_file), listing directories (use list_dir), '
                    'searching file contents (use grep), or editing files (use edit_file/write_file). '
                    f'Commands are subject to a {self.DEFAULT_TIMEOUT}s timeout.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'command': {'type': 'string', 'description': ('The shell command to execute. e.g. "ls -la" or "python script.py". Supports pipes and redirects via shell when metacharacters are present.')},
                        'working_dir': {'type': 'string', 'description': 'Optional working directory. Defaults to the current directory.'},
                        'timeout': {'type': 'integer', 'description': f'Timeout in seconds (default {self.DEFAULT_TIMEOUT}, max 300).'},
                    },
                    'required': ['command'],
                },
            },
        }

    @staticmethod
    def _parse_args(**kwargs: Any) -> tuple[str, str | None, int, str | None]:
        command = str(kwargs.get('command', ''))
        working_dir = str(kwargs.get('working_dir', '')) or None
        timeout = int(kwargs.get('timeout', 0)) or Exec.DEFAULT_TIMEOUT

        if not command.strip():
            return '', None, 0, 'Error: command is required'

        if len(command) > _MAX_COMMAND_LENGTH:
            return '', None, 0, f'Error: command too long ({len(command)} chars, max {_MAX_COMMAND_LENGTH})'

        timeout = min(max(timeout, 1), 300)

        cwd = None
        if working_dir:
            cwd = os.path.abspath(os.path.expanduser(working_dir))
            if not os.path.isdir(cwd):
                return '', None, 0, f'Error: working_dir does not exist: {cwd}'

        return command, cwd, timeout, None

    async def run(self, **kwargs: Any) -> str:
        command, cwd, timeout, error = self._parse_args(**kwargs)
        if error:
            return error

        env = _build_env()

        if _needs_shell(command):
            try:
                proc = await asyncio.create_subprocess_shell(command, cwd=cwd, env=env, start_new_session=True, **_spawn_kwargs(asyncio.subprocess.DEVNULL))
            except OSError as e:
                return f'Error: cannot execute command: {e}'
        else:
            try:
                args = shlex.split(command)
            except ValueError as e:
                return f'Error: cannot parse command: {e}'
            try:
                proc = await asyncio.create_subprocess_exec(*args, cwd=cwd, env=env, start_new_session=True, **_spawn_kwargs(asyncio.subprocess.DEVNULL))
            except FileNotFoundError:
                return f'Error: command not found: {args[0]}'
            except OSError as e:
                return f'Error: cannot execute command: {e}'

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            await _kill_proc(proc)
            return f'Error: command timed out after {timeout}s'

        stdout = _decode_output(stdout_bytes)
        stderr = _decode_output(stderr_bytes)
        return_code = proc.returncode or 0
        return _format_output(stdout, stderr, return_code)
