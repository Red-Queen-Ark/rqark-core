import sys

from rqark_core.types.prompt import BasePrompt, PromptContext

_PLATFORM_HINTS: dict[str, str] = {
    'win32': ('You are running on Windows. Use Windows-style paths with backslashes, and prefer PowerShell/CMD syntax for shell commands. The exec/shell tools use cmd.exe by default.'),
    'darwin': ('You are running on macOS. Use Unix-style paths with forward slashes, and prefer bash/zsh syntax for shell commands.'),
    'linux': ('You are running on Linux. Use Unix-style paths with forward slashes, and prefer bash/sh syntax for shell commands.'),
}


class PlatformPrompt(BasePrompt):
    priority = 30

    async def get_messages(self, ctx: PromptContext | None = None) -> str:
        hint = _PLATFORM_HINTS.get(sys.platform, f'You are running on an unknown platform ({sys.platform}).')
        return f'## Platform\n{hint}'
