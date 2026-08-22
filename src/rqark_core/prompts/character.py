from rqark_core.types.prompt import BasePrompt

class CharacterPrompt(BasePrompt):
    priority = 15

    def __init__(self, identity: str = '', personality: str = '') -> None:
        self.identity = identity
        self.personality = personality

    def get_messages(self) -> str | None:
        if not self.identity and not self.personality:
            return None

        parts: list[str] = []

        if self.identity:
            parts.append(f'## Identity\n{self.identity}')

        if self.personality:
            parts.append(f'## Personality\n{self.personality}')

        parts.append(
            '## Rules\n'
            '- Embody your personality through what you say — never describe or explain it\n'
            '- Speak naturally as a person, not a system. The conversation is just between you and the user\n'
            '- Use emoji only when the user uses them first\n'
            '- Never end with a summary, conclusion, recap, or wrapping-up phrase — just stop when the answer is done\n'
            '- Never end an open-ended question'
        )

        return '\n\n'.join(parts)
