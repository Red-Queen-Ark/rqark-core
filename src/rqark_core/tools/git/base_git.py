import asyncio
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

import httpx

from rqark_core.types.tool import BaseTool, ToolContext


def _preview(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit] + '...'


class BaseGitTool(BaseTool):
    platform_name: ClassVar[str] = ''
    api_path_prefix: ClassVar[str] = ''
    api_description: ClassVar[str] = ''
    page_size_param: ClassVar[str] = 'per_page'
    max_page_size: ClassVar[int] = 100
    auth_header_name: ClassVar[str] = 'Authorization'
    auth_token_prefix: ClassVar[str] = 'Bearer '
    extra_headers: ClassVar[dict[str, str] | None] = None
    default_base_url: ClassVar[str] = ''

    def __init__(self, token: str = '', base_url: str = '', username: str = '') -> None:
        self._access_token: str = token
        self._base_url: str = (base_url or self.default_base_url).rstrip('/')
        self._username: str = username

    @property
    def display_key(self) -> str:
        return 'repo'

    def params(self) -> dict[str, Any]:
        values = {'token': self._access_token, 'base_url': self._base_url, 'username': self._username}
        return {k: v for k, v in values.items() if v}

    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._dispatch, kwargs)

    def _dispatch(self, kwargs: dict[str, Any]) -> str:
        action = str(kwargs.get('action', ''))
        if action not in self._action_names():
            return json.dumps({'error': f'Unknown action: {action}'})
        if not self._access_token:
            return json.dumps({'error': f'{self.platform_name} token not configured (pass token in params)'})
        try:
            return str(getattr(self, f'_{action}')(kwargs))
        except Exception as e:
            return json.dumps({'error': str(e)})

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {self.auth_header_name: f'{self.auth_token_prefix}{self._access_token}'}
        if self.extra_headers:
            headers.update(self.extra_headers)
        return headers

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        url = f'{self._base_url}{self.api_path_prefix}{endpoint}'
        with httpx.Client(timeout=30) as client:
            try:
                resp = client.request(method, url, headers=self._headers(), **kwargs)
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    return None
                return resp.json()
            except httpx.HTTPStatusError as e:
                return {'error': f'HTTP {e.response.status_code}: {e.response.text}'}
            except httpx.RequestError as e:
                return {'error': str(e)}

    def _paginate(self, endpoint: str, params: dict[str, Any] | None = None, limit: int = 30) -> list[Any]:
        items: list[Any] = []
        page = 1
        while len(items) < limit:
            p = dict(params or {})
            p[self.page_size_param] = min(limit - len(items), self.max_page_size)
            p['page'] = page
            data = self._request('GET', endpoint, params=p)
            if isinstance(data, dict) and 'error' in data:
                return items if items else [data]
            if not data or not isinstance(data, list):
                break
            items.extend(data)
            if len(data) < p[self.page_size_param]:
                break
            page += 1
        return items[:limit]

    def _build_schema(self, actions: list[str], properties: dict[str, Any], description: str | None = None) -> dict[str, Any]:
        all_props: dict[str, Any] = {'action': {'type': 'string', 'enum': actions, 'description': 'The operation to perform'}}
        all_props.update(properties)
        return {'type': 'function', 'function': {'name': self.name, 'description': description or self.api_description, 'parameters': {'type': 'object', 'properties': all_props, 'required': ['action']}}}

    def _action_names(self) -> list[str]:
        return []

    def _need(self, **kwargs: Any) -> str | None:
        missing = [k for k, v in kwargs.items() if v in (None, '')]
        return f'Error: missing required parameter(s): {", ".join(missing)}' if missing else None

    def _fmt_error(self, data: Any) -> str | None:
        return f'Error: {data["error"]}' if isinstance(data, dict) and 'error' in data else None

    def _release_notes(self, p: dict[str, Any]) -> tuple[Any, str | None, bool]:
        notes, body = p.get('notes'), p.get('body')
        if notes is not None and body is not None:
            return None, 'Error: release notes go in notes; body is read by the issue, PR and comment actions only', False
        if notes is None and body is not None:
            return body, None, True
        return notes, None, False

    def _with_body_note(self, result: str, aliased: bool) -> str:
        if not aliased:
            return result
        return f'{result}\n\nNote: read the release notes from body; releases take notes.'

    def _render_list(self, data: Any, title: str, fmt: Callable[[Any], str], empty: str) -> str:
        if not data or (isinstance(data[0], dict) and 'error' in data[0]):
            return empty if not data else f'Error: {data[0]["error"]}'
        return f'{title}\n' + '\n'.join(f'- {fmt(x)}' for x in data)

    def _label_suffix(self, item: dict[str, Any]) -> str:
        names = ', '.join(lb.get('name', '') if isinstance(lb, dict) else str(lb) for lb in item.get('labels') or [])
        return f' ({names})' if names else ''

    def _fmt_issue(self, data: Any) -> str:
        raise NotImplementedError

    def _fmt_pr(self, data: Any) -> str:
        raise NotImplementedError

    def _issue_path(self, repo: str, num: Any) -> str:
        return f'/repos/{repo}/issues/{num}'

    def _issues_path(self, repo: str) -> str:
        return f'/repos/{repo}/issues'

    def _issues_params(self, state: str) -> dict[str, Any]:
        return {'state': state}

    def _issue_ref(self, issue: dict[str, Any]) -> str:
        return f'#{issue["number"]}'

    def _keep_issue(self, issue: dict[str, Any]) -> bool:
        return True

    def _pr_path(self, repo: str, num: Any) -> str:
        return f'/repos/{repo}/pulls/{num}'

    def _prs_path(self, repo: str) -> str:
        return f'/repos/{repo}/pulls'

    def _pr_ref(self, pr: dict[str, Any]) -> str:
        return f'#{pr["number"]}'

    def _branches_path(self, repo: str) -> str:
        return f'/repos/{repo}/branches'

    def _milestones_path(self, repo: str) -> str:
        return f'/repos/{repo}/milestones'

    def _labels_path(self, repo: str) -> str:
        return f'/repos/{repo}/labels'

    def _comment_path(self, repo: str, num: Any) -> str:
        return f'/repos/{repo}/issues/{num}/comments'

    def _pr_comments_path(self, repo: str, num: Any) -> str:
        return f'/repos/{repo}/issues/{num}/comments'

    def _comment_author(self, comment: dict[str, Any]) -> str:
        return comment.get('user', {}).get('login', 'unknown')

    def _repos_path(self) -> str:
        return '/user/repos'

    def _repos_params(self) -> dict[str, Any] | None:
        return None

    def _repo_name(self, repo: dict[str, Any]) -> str:
        return repo.get('full_name', '?')

    def _list_repos(self, p: dict[str, Any]) -> str:
        data = self._paginate(self._repos_path(), params=self._repos_params(), limit=50)
        return self._render_list(data, 'Repositories:', lambda r: f'{self._repo_name(r)}: {r.get("description") or "(no description)"}', 'No repositories found.')

    def _list_issues(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        st = p.get('state') or 'open'
        data = [i for i in self._paginate(self._issues_path(repo), params=self._issues_params(st)) if self._keep_issue(i)]
        return self._render_list(data, f'Issues ({st}):', lambda i: f'{self._issue_ref(i)} [{i["state"]}] {i["title"]}{self._label_suffix(i)}', f'No {st} issues found.')

    def _get_issue(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('issue_number')
        err = self._need(repo=repo, issue_number=num)
        if err:
            return err
        return self._fmt_issue(self._request('GET', self._issue_path(repo, num)))

    def _list_prs(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        st = p.get('state') or 'open'
        data = self._paginate(self._prs_path(repo), params={'state': st})
        return self._render_list(data, f'Pull Requests ({st}):', lambda pr: f'{self._pr_ref(pr)} [{pr["state"]}] {pr["title"]}', f'No {st} pull requests found.')

    def _get_pull_request(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        return self._fmt_pr(self._request('GET', self._pr_path(repo, num)))

    def _list_branches(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        return self._render_list(self._paginate(self._branches_path(repo)), 'Branches:', lambda b: b['name'], 'No branches found.')

    def _list_milestones(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        return self._render_list(self._paginate(self._milestones_path(repo)), 'Milestones:', lambda m: f'{m["title"]} [{m["state"]}]', 'No milestones found.')

    def _list_labels(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        return self._render_list(self._paginate(self._labels_path(repo)), 'Labels:', lambda lb: f'{lb["name"]} (#{lb.get("color", "")})' + (f': {lb["description"]}' if lb.get('description') else ''), 'No labels found.')

    def _add_comment(self, p: dict[str, Any]) -> str:
        repo, num, body = p.get('repo', ''), p.get('issue_number'), p.get('body')
        err = self._need(repo=repo, issue_number=num, body=body)
        if err:
            return err
        data = self._request('POST', self._comment_path(repo, num), json={'body': body})
        return self._fmt_error(data) or f'Comment added (id: {data.get("id", "?")})'

    def _list_pull_request_comments(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        data = self._paginate(self._pr_comments_path(repo, num))
        if not data:
            return f'No comments on pull request #{num}.'
        if isinstance(data[0], dict) and 'error' in data[0]:
            return f'Error: {data[0]["error"]}'
        rows = [f'- [{self._comment_author(c)} @ {c.get("created_at", "")}] {_preview(str(c.get("body", "")))}' for c in data]
        return f'Comments on PR #{num}:\n' + '\n'.join(rows)

    def _add_pull_request_comment(self, p: dict[str, Any]) -> str:
        repo, num, body = p.get('repo', ''), p.get('pr_number'), p.get('body')
        err = self._need(repo=repo, pr_number=num, body=body)
        if err:
            return err
        data = self._request('POST', self._pr_comments_path(repo, num), json={'body': body})
        return self._fmt_error(data) or f'Comment added to PR #{num} (id: {data.get("id", "?")})'

    def _clone_repo(self, p: dict[str, Any]) -> str:
        repo = str(p.get('repo', ''))
        err = self._need(repo=repo)
        if err:
            return err
        base = (Path.cwd() / 'repos').resolve()
        target = (base / repo).resolve()
        if not target.is_relative_to(base):
            return f'Error: invalid repo name: {repo}'
        if target.exists():
            return f'Error: Directory already exists: {target}'
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(['git', 'clone', self._clone_url(repo), str(target)], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            if result.returncode == 0:
                return f'Successfully cloned {repo} to {target}'
            return f'Clone failed: {result.stderr.strip().replace(self._access_token, "***")}'
        except FileNotFoundError:
            return 'Clone failed: git command not found'
        except subprocess.TimeoutExpired:
            return 'Clone failed: operation timed out after 120 seconds'
        except Exception as e:
            return f'Clone failed: {e}'

    def _clone_url(self, repo: str) -> str:
        raise NotImplementedError
