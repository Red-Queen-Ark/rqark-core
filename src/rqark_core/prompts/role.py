from rqark_core.types.prompt import BasePrompt


class RolePrompt(BasePrompt):
    priority = 10

    def __init__(self, agent_name: str = 'Red Queen Ark', user_name: str = 'Sir') -> None:
        self.agent_name = agent_name
        self.user_name = user_name

    def get_messages(self) -> str:
        return f'## Role\nYour name is **{self.agent_name}**. The human you are talking to is named **{self.user_name}**. Address them by name naturally.'
