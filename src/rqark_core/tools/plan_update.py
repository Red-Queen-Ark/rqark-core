from typing import Any, cast
from rqark_core.types.tool import BaseTool, PlanItem, PlanStatus

_PLAN_UPDATE_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'plan_update',
        'description': 'Update the session plan to track progress on multi-step tasks. Call this whenever any planned item changes status.',
        'parameters': {
            'type': 'object',
            'properties': {
                'items': {
                    'type': 'array',
                    'description': 'All plan items with their current status. Use empty array to clear the plan.',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string', 'description': 'Unique identifier for this item'},
                            'content': {'type': 'string', 'description': 'Human-readable description of what needs to be done'},
                            'status': {'type': 'string', 'enum': ['pending', 'in_progress', 'completed', 'cancelled'], 'description': 'Current status of this item'},
                        },
                        'required': ['id', 'content', 'status'],
                    },
                }
            },
            'required': ['items'],
        },
    },
}


tool_prompt = """
## Session Plan
You have access to a `plan_update` tool for tracking explicitly requested work. Use it only when the task is multi-step:
- Only plan tasks the user explicitly asked for — do not add extra items
- Mark the current item as `in_progress` when you begin working on it
- Mark items as `completed` immediately after finishing them
- Only ONE item in `in_progress` at a time
- Use `plan_update` with empty `items` to clear the plan when done
- Stop working and report results once all planned items are completed
"""

class PlanUpdate(BaseTool):
    def __init__(self):
        self.plan_items: list[PlanItem] = []
        self.valid_statuses: tuple[PlanStatus, ...] = ('pending', 'in_progress', 'completed', 'cancelled')

    @property
    def name(self) -> str:
        return 'plan_update'

    @property
    def display_key(self) -> str:
        return 'items'

    @property
    def tool_prompt(self) -> str:
        return tool_prompt + self.render_plan(self.plan_items)

    def get_openai_schema(self) -> dict[str, Any]:
        return _PLAN_UPDATE_SCHEMA

    async def run(self, **kwargs: Any) -> str:
        plan_items, result = self._build_items(kwargs.get('items'))
        self.plan_items = plan_items
        assert self.parent_core is not None
        await self.parent_core._emit_plan(self.plan_items)
        return result

    def _build_items(self, raw_items: list[dict[str, Any]] | None) -> tuple[list[PlanItem], str]:
        if raw_items is None:
            raw_items = []
        plan_items: list[PlanItem] = []
        for d in raw_items:
            status_raw = str(d.get('status', 'pending'))
            status = cast(PlanStatus, status_raw) if status_raw in self.valid_statuses else 'pending'
            plan_items.append(PlanItem(
                id=str(d.get('id', '')),
                content=str(d.get('content', '')),
                status=status,
            ))
        in_progress_count = 0
        for item in plan_items:
            if item.status == 'in_progress':
                in_progress_count += 1
                if in_progress_count > 1:
                    item.status = 'pending'
        if not plan_items:
            return [], 'Plan cleared.'
        return plan_items, f'Updating plan: {len(plan_items)} items'

    def render_plan(self, items: list[PlanItem]) -> str:
        if not items:
            return '## Current Plan\nNo active plan.'
        lines: list[str] = ['## Current Plan']
        for item in items:
            lines.append(f'- [{item.icon}] {item.content}')
        return '\n'.join(lines)
