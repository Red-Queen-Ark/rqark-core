from typing import Any

import pytest

from rqark_core.tools.git.gitea import Gitea
from rqark_core.tools.git.github import GitHub
from rqark_core.tools.git.gitlab import GitLab

TOOLS = [Gitea, GitHub, GitLab]
NOTES_FIELD = {Gitea: 'body', GitHub: 'body', GitLab: 'description'}
RELEASE_REF = {Gitea: {'release_id': 7}, GitHub: {'release_id': 7}, GitLab: {'tag': 'v1'}}

NOTES = '### New\n- a thing'
RELEASE = {'tag_name': 'v1', 'name': 'v1', 'created_at': '2026-10-16T00:00:00Z', 'published_at': '2026-10-16T00:00:00Z', 'body': NOTES, 'description': NOTES}


def build(tool_class: type) -> tuple[Any, list[tuple[str, str, Any]]]:
    tool = tool_class(token='tok', base_url='https://git.test')
    calls: list[tuple[str, str, Any]] = []

    def request(method: str, endpoint: str, **kwargs: Any) -> Any:
        calls.append((method, endpoint, kwargs.get('json')))
        return dict(RELEASE)

    setattr(tool, '_request', request)
    return tool, calls


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_create_release_sends_the_notes(tool_class):
    tool, calls = build(tool_class)

    result = await tool.run(action='create_release', repo='o/r', tag='v1', release_name='v1', notes=NOTES)

    method, _endpoint, payload = calls[0]
    assert method == 'POST'
    assert payload['tag_name'] == 'v1'
    assert payload[NOTES_FIELD[tool_class]] == NOTES
    assert NOTES in result
    assert 'from body' not in result


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_create_release_takes_notes_sent_as_body(tool_class):
    tool, calls = build(tool_class)

    result = await tool.run(action='create_release', repo='o/r', tag='v1', body=NOTES)

    method, _endpoint, payload = calls[0]
    assert method == 'POST'
    assert payload[NOTES_FIELD[tool_class]] == NOTES
    assert NOTES in result
    assert 'from body' in result


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_update_release_sends_the_notes(tool_class):
    tool, calls = build(tool_class)

    await tool.run(action='update_release', repo='o/r', notes=NOTES, **RELEASE_REF[tool_class])

    _method, _endpoint, payload = calls[0]
    assert payload[NOTES_FIELD[tool_class]] == NOTES


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_update_release_takes_notes_sent_as_body(tool_class):
    tool, calls = build(tool_class)

    result = await tool.run(action='update_release', repo='o/r', body=NOTES, **RELEASE_REF[tool_class])

    _method, _endpoint, payload = calls[0]
    assert payload[NOTES_FIELD[tool_class]] == NOTES
    assert 'from body' in result


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_release_notes_are_never_dropped_silently(tool_class):
    tool, calls = build(tool_class)

    result = await tool.run(action='create_release', repo='o/r', tag='v1', notes=NOTES, body='something else')

    assert 'notes' in result
    assert calls == []


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_update_release_clears_the_notes_with_an_empty_notes(tool_class):
    tool, calls = build(tool_class)

    await tool.run(action='update_release', repo='o/r', notes='', **RELEASE_REF[tool_class])

    _method, _endpoint, payload = calls[0]
    assert payload[NOTES_FIELD[tool_class]] == ''


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_create_issue_still_takes_its_body(tool_class):
    tool, calls = build(tool_class)

    await tool.run(action='create_issue', repo='o/r', title='T', body='hello')

    assert 'hello' in str(calls[0][2])


@pytest.mark.parametrize('tool_class', TOOLS)
async def test_add_comment_still_takes_its_body(tool_class):
    tool, calls = build(tool_class)

    await tool.run(action='add_comment', repo='o/r', issue_number=1, body='hello')

    assert 'hello' in str(calls[0][2])


@pytest.mark.parametrize('tool_class', TOOLS)
def test_the_schema_stops_offering_body_for_release_notes(tool_class):
    properties = tool_class(token='tok').get_openai_schema()['function']['parameters']['properties']

    assert 'release' not in properties['body']['description']
    assert 'create_release' in properties['notes']['description']
