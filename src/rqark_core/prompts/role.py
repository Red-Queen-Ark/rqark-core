from rqark_core.types.prompt import BasePrompt, PromptContext


class RolePrompt(BasePrompt):
    priority = 10

    def __init__(self, agent_name: str = 'Red Queen Ark', user_name: str = 'Sir') -> None:
        self.agent_name = agent_name
        self.user_name = user_name

    async def get_messages(self, ctx: PromptContext | None = None) -> str:
        return f'## Role\nYour name is **{self.agent_name}**. The human you are talking to is named **{self.user_name}**. Address them by name naturally.'

    def params(self) -> dict[str, str]:
        return {'agent_name': self.agent_name, 'user_name': self.user_name}
