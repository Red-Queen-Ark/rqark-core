from typing import Any
from urllib.parse import urlsplit

from rqark_core.tools.git.base_git import BaseGitTool, _preview


def _pid(repo: str) -> str:
    return repo.replace('/', '%2F')


class GitLab(BaseGitTool):
    platform_name = 'GitLab'
    api_path_prefix = '/api/v4'
    api_description = 'Interact with GitLab: list/clone repos, manage issues, MRs, milestones, labels, branches, releases, commits, and compare.'
    auth_header_name = 'PRIVATE-TOKEN'
    auth_token_prefix = ''
    default_base_url = 'https://gitlab.com'

    @property
    def name(self) -> str:
        return 'gitlab'

    def _action_names(self) -> list[str]:
        return ['list_repos', 'clone_repo', 'list_issues', 'list_prs', 'get_issue', 'create_issue', 'update_issue', 'add_comment', 'list_milestones', 'list_labels', 'list_branches', 'get_pull_request', 'create_pull_request', 'update_pull_request', 'merge_pull_request', 'close_pull_request', 'list_pull_request_comments', 'add_pull_request_comment', 'list_releases', 'get_release', 'create_release', 'update_release', 'delete_release', 'list_commits', 'compare']

    def get_openai_schema(self) -> dict[str, Any]:
        props = {
            'repo': {'type': 'string', 'description': 'Repository (namespace/project format)'},
            'issue_number': {'type': 'integer', 'description': 'Issue IID'},
            'state': {'type': 'string', 'enum': ['open', 'closed', 'all'], 'description': 'Filter by state'},
            'title': {'type': 'string', 'description': 'Title for issue/MR/release'},
            'body': {'type': 'string', 'description': 'Body text for issue/MR/comment'},
            'assignee': {'type': 'string', 'description': 'Username to assign'},
            'pr_number': {'type': 'integer', 'description': 'Merge request IID'},
            'head': {'type': 'string', 'description': 'Source branch for MR'},
            'base': {'type': 'string', 'description': 'Target branch for MR (e.g. main)'},
            'delete_branch': {'type': 'boolean', 'description': 'Delete source branch after merge'},
            'tag': {'type': 'string', 'description': 'Tag name for the release'},
            'release_name': {'type': 'string', 'description': 'Release title'},
            'notes': {'type': 'string', 'description': 'Release notes (create_release, update_release)'},
            'per_page': {'type': 'integer', 'description': 'Number of commits to list (max 100)'},
            'ref_name': {'type': 'string', 'description': 'Branch or tag to list commits from'},
            'since': {'type': 'string', 'description': 'Only commits after this ISO 8601 date'},
            'from_ref': {'type': 'string', 'description': 'Source ref for compare'},
            'to_ref': {'type': 'string', 'description': 'Target ref for compare'},
        }
        return self._build_schema(self._action_names(), props)

    def _clone_url(self, repo: str) -> str:
        host = urlsplit(self._base_url).netloc or 'gitlab.com'
        return f'https://oauth2:{self._access_token}@{host}/{repo}.git'

    def _issue_path(self, repo: str, num: Any) -> str:
        return f'/projects/{_pid(repo)}/issues/{num}'

    def _issues_path(self, repo: str) -> str:
        return f'/projects/{_pid(repo)}/issues'

    def _issue_ref(self, issue: dict[str, Any]) -> str:
        return f'#{issue["iid"]}'

    def _keep_issue(self, issue: dict[str, Any]) -> bool:
        return issue.get('type') != 'MergeRequest'

    def _pr_path(self, repo: str, num: Any) -> str:
        return f'/projects/{_pid(repo)}/merge_requests/{num}'

    def _prs_path(self, repo: str) -> str:
        return f'/projects/{_pid(repo)}/merge_requests'

    def _pr_ref(self, pr: dict[str, Any]) -> str:
        return f'!{pr["iid"]}'

    def _branches_path(self, repo: str) -> str:
        return f'/projects/{_pid(repo)}/repository/branches'

    def _milestones_path(self, repo: str) -> str:
        return f'/projects/{_pid(repo)}/milestones'

    def _labels_path(self, repo: str) -> str:
        return f'/projects/{_pid(repo)}/labels'

    def _comment_path(self, repo: str, num: Any) -> str:
        return f'/projects/{_pid(repo)}/issues/{num}/notes'

    def _pr_comments_path(self, repo: str, num: Any) -> str:
        return f'/projects/{_pid(repo)}/merge_requests/{num}/notes'

    def _comment_author(self, comment: dict[str, Any]) -> str:
        return comment.get('author', {}).get('name', 'unknown')

    def _repos_path(self) -> str:
        return '/projects'

    def _repos_params(self) -> dict[str, Any] | None:
        return {'membership': 'true'}

    def _repo_name(self, repo: dict[str, Any]) -> str:
        return repo['path_with_namespace']

    def _assignee_ids(self, assignee: str | None) -> list[int]:
        if not assignee:
            return []
        users = self._request('GET', '/users', params={'username': assignee})
        return [users[0]['id']] if isinstance(users, list) and users else []

    def _create_issue(self, p: dict[str, Any]) -> str:
        repo, title, body, assignee = p.get('repo', ''), p.get('title'), p.get('body'), p.get('assignee')
        err = self._need(repo=repo, title=title)
        if err:
            return err
        payload: dict[str, Any] = {'title': title, 'description': body or ''}
        ids = self._assignee_ids(assignee)
        if ids:
            payload['assignee_ids'] = ids
        return self._fmt_issue(self._request('POST', f'/projects/{_pid(repo)}/issues', json=payload))

    def _update_issue(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('issue_number')
        err = self._need(repo=repo, issue_number=num)
        if err:
            return err
        payload: dict[str, Any] = {}
        if p.get('title') is not None:
            payload['title'] = p['title']
        if p.get('body') is not None:
            payload['description'] = p['body']
        if p.get('state') in ('open', 'closed'):
            payload['state_event'] = 'reopen' if p['state'] == 'open' else 'close'
        if p.get('assignee') is not None:
            payload['assignee_ids'] = self._assignee_ids(p['assignee'])
        if not payload:
            return 'Error: nothing to update'
        return self._fmt_issue(self._request('PUT', f'/projects/{_pid(repo)}/issues/{num}', json=payload))

    def _create_pull_request(self, p: dict[str, Any]) -> str:
        repo, title, body, head, base, assignee = p.get('repo', ''), p.get('title'), p.get('body'), p.get('head'), p.get('base'), p.get('assignee')
        err = self._need(repo=repo, title=title, head=head, base=base)
        if err:
            return err
        payload: dict[str, Any] = {'title': title, 'description': body or '', 'source_branch': head, 'target_branch': base}
        ids = self._assignee_ids(assignee)
        if ids:
            payload['assignee_ids'] = ids
        return self._fmt_pr(self._request('POST', f'/projects/{_pid(repo)}/merge_requests', json=payload))

    def _update_pull_request(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        payload: dict[str, Any] = {}
        if p.get('title') is not None:
            payload['title'] = p['title']
        if p.get('body') is not None:
            payload['description'] = p['body']
        if p.get('state') in ('open', 'closed'):
            payload['state_event'] = 'reopen' if p['state'] == 'open' else 'close'
        if p.get('assignee') is not None:
            payload['assignee_ids'] = self._assignee_ids(p['assignee'])
        if not payload:
            return 'Error: nothing to update'
        return self._fmt_pr(self._request('PUT', f'/projects/{_pid(repo)}/merge_requests/{num}', json=payload))

    def _merge_pull_request(self, p: dict[str, Any]) -> str:
        repo, num, delete_branch = p.get('repo', ''), p.get('pr_number'), p.get('delete_branch')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        data = self._request('PUT', f'/projects/{_pid(repo)}/merge_requests/{num}/merge')
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        result = f'Merge request !{num} merged successfully.'
        if delete_branch and isinstance(data, dict) and data.get('source_branch'):
            branch = data['source_branch']
            self._request('DELETE', f'/projects/{_pid(repo)}/repository/branches/{branch}')
            result += f' Deleted branch {branch}.'
        return result

    def _close_pull_request(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        return self._fmt_pr(self._request('PUT', f'/projects/{_pid(repo)}/merge_requests/{num}', json={'state_event': 'close'}))

    def _list_releases(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        data = self._paginate(f'/projects/{_pid(repo)}/releases')
        return self._render_list(data, 'Releases:', lambda r: f'{r["tag_name"]}: {r.get("name") or "(untitled)"}  [{r.get("created_at", "")}] {_preview(r.get("description") or "", 150)}', 'No releases found.')

    def _get_release(self, p: dict[str, Any]) -> str:
        repo, tag = p.get('repo', ''), p.get('tag')
        err = self._need(repo=repo, tag=tag)
        if err:
            return err
        return self._fmt_release(self._request('GET', f'/projects/{_pid(repo)}/releases/{tag}'))

    def _create_release(self, p: dict[str, Any]) -> str:
        repo, tag, name = p.get('repo', ''), p.get('tag'), p.get('release_name')
        notes, body_err, aliased = self._release_notes(p)
        err = self._need(repo=repo, tag=tag) or body_err
        if err:
            return err
        payload: dict[str, Any] = {'name': name or tag, 'tag_name': tag, 'description': notes or ''}
        data = self._request('POST', f'/projects/{_pid(repo)}/releases', json=payload)
        return self._with_body_note(self._fmt_release(data), aliased)

    def _update_release(self, p: dict[str, Any]) -> str:
        repo, tag = p.get('repo', ''), p.get('tag')
        notes, body_err, aliased = self._release_notes(p)
        err = self._need(repo=repo, tag=tag) or body_err
        if err:
            return err
        payload: dict[str, Any] = {}
        if p.get('release_name') is not None:
            payload['name'] = p['release_name']
        if notes is not None:
            payload['description'] = notes
        if not payload:
            return 'Error: nothing to update'
        return self._with_body_note(self._fmt_release(self._request('PUT', f'/projects/{_pid(repo)}/releases/{tag}', json=payload)), aliased)

    def _delete_release(self, p: dict[str, Any]) -> str:
        repo, tag = p.get('repo', ''), p.get('tag')
        err = self._need(repo=repo, tag=tag)
        if err:
            return err
        data = self._request('DELETE', f'/projects/{_pid(repo)}/releases/{tag}')
        return self._fmt_error(data) or f'Release {tag} deleted successfully.'

    def _list_commits(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        per_page = min(int(p.get('per_page') or 20), 100)
        params: dict[str, Any] = {'per_page': per_page}
        if p.get('ref_name'):
            params['ref_name'] = p['ref_name']
        if p.get('since'):
            params['since'] = p['since']
        data = self._paginate(f'/projects/{_pid(repo)}/repository/commits', params=params, limit=per_page)
        return self._render_list(data, 'Commits:', lambda c: f'{c.get("short_id", "?")} | {(c.get("committed_date") or "?")[:10]} | {c.get("author_name", "unknown")} | {c.get("title", c.get("message", "(no message)"))[:80]}', 'No commits found.')

    def _compare(self, p: dict[str, Any]) -> str:
        repo, frm, to = p.get('repo', ''), p.get('from_ref'), p.get('to_ref')
        err = self._need(repo=repo, from_ref=frm, to_ref=to)
        if err:
            return err
        data = self._request('GET', f'/projects/{_pid(repo)}/repository/compare', params={'from': frm, 'to': to})
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        commits = data.get('commits', [])
        diffs = data.get('diffs', [])
        lines = [f'Compare: {frm}...{to}', f'Commits ({len(commits)}):']
        lines += [f'- {c.get("short_id", "?")} | {(c.get("committed_date") or "?")[:10]} | {c.get("author_name", "unknown")} | {c.get("title", "(no message)")}' for c in commits[:30]]
        lines += [f'Diffs ({len(diffs)} files):']
        lines += [f'- {d.get("new_path", d.get("old_path", "?"))}' for d in diffs[:30]]
        return '\n'.join(lines)

    def _fmt_issue(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        labels = ', '.join(data.get('labels', [])) if data.get('labels') else ''
        assignee_name = data.get('assignee', {}).get('name', '') if isinstance(data.get('assignee'), dict) else ''
        author_name = data.get('author', {}).get('name', 'unknown') if isinstance(data.get('author'), dict) else ''
        lines = [f'Issue !{data["iid"]}: {data["title"]}', f'State: {data["state"]}', f'Author: {author_name}', f'Created: {data["created_at"]}', '', data.get('description') or '(no description)']
        if assignee_name:
            lines.append(f'Assignee: {assignee_name}')
        if labels:
            lines.append(f'Labels: {labels}')
        return '\n'.join(lines)

    def _fmt_pr(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        author_name = data.get('author', {}).get('name', 'unknown') if isinstance(data.get('author'), dict) else 'unknown'
        lines = [f'MR !{data["iid"]}: {data["title"]}', f'State: {data["state"]}', f'Author: {author_name}', f'Branch: {data["source_branch"]} -> {data["target_branch"]}', f'Created: {data["created_at"]}', '', data.get('description') or '(no description)']
        if data.get('merge_status'):
            lines.append(f'Merge Status: {data["merge_status"]}')
        return '\n'.join(lines)

    def _fmt_release(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        return '\n'.join([f'Release: {data["tag_name"]}', f'Title: {data.get("name") or "(untitled)"}', f'Created: {data.get("created_at", "")}', '', data.get('description') or '(no release notes)'])
