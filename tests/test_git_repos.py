from typing import Any

import pytest

from rqark_core.tools.git.gitea import Gitea
from rqark_core.tools.git.github import GitHub
from rqark_core.tools.git.gitlab import GitLab

TOOLS = [Gitea, GitHub, GitLab]
NAME_FIELD = {Gitea: 'full_name', GitHub: 'full_name', GitLab: 'path_with_namespace'}

REPOS = [
    {NAME_FIELD[Gitea]: 'o/live', NAME_FIELD[GitHub]: 'o/live', NAME_FIELD[GitLab]: 'o/live', 'description': 'a live one', 'archived': False},
    {NAME_FIELD[Gitea]: 'o/dead', NAME_FIELD[GitHub]: 'o/dead', NAME_FIELD[GitLab]: 'o/dead', 'description': 'a dead one', 'archived': True},
]


def build(tool_class: type) -> Any:
    tool = tool_class(token='tok', base_url='https://git.test')
    setattr(tool, '_request', lambda method, endpoint, **kwargs: [dict(r) for r in REPOS])
    return tool


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_list_repos_marks_archived_repos(tool_class):
    tool = build(tool_class)

    result = await tool.run(action='list_repos')

    assert '- o/dead [ARCHIVED]: a dead one' in result
    assert '- o/live: a live one' in result


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_list_repos_tolerates_a_missing_archived_field(tool_class):
    tool = build(tool_class)
    setattr(tool, '_request', lambda method, endpoint, **kwargs: [{'full_name': 'o/r', 'path_with_namespace': 'o/r'}])

    result = await tool.run(action='list_repos')

    assert 'ARCHIVED' not in result
