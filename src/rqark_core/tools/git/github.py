from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from rqark_core.tools.git.base_git import BaseGitTool


class GitHub(BaseGitTool):
    platform_name = 'GitHub'
    api_path_prefix = ''
    api_description = 'Interact with GitHub: list/clone repos, manage issues, PRs, milestones, labels, branches, and releases.'
    default_base_url = 'https://api.github.com'
    extra_headers = {'Accept': 'application/vnd.github.v3+json'}

    @property
    def name(self) -> str:
        return 'github'

    def _action_names(self) -> list[str]:
        return [
            'list_repos',
            'clone_repo',
            'list_issues',
            'list_prs',
            'get_issue',
            'create_issue',
            'update_issue',
            'add_comment',
            'list_milestones',
            'list_labels',
            'list_branches',
            'get_pull_request',
            'create_pull_request',
            'update_pull_request',
            'merge_pull_request',
            'close_pull_request',
            'list_pull_request_comments',
            'add_pull_request_comment',
            'list_releases',
            'get_release',
            'create_release',
            'update_release',
            'delete_release',
        ]

    def get_openai_schema(self) -> dict[str, Any]:
        props = {
            'repo': {'type': 'string', 'description': 'Repository (owner/repo format)'},
            'issue_number': {'type': 'integer', 'description': 'Issue number'},
            'state': {'type': 'string', 'enum': ['open', 'closed', 'all'], 'description': 'Filter by state'},
            'title': {'type': 'string', 'description': 'Title for issue/PR/release'},
            'body': {'type': 'string', 'description': 'Body text for issue/PR/comment'},
            'assignee': {'type': 'string', 'description': 'Username to assign'},
            'pr_number': {'type': 'integer', 'description': 'Pull request number'},
            'head': {'type': 'string', 'description': 'Source branch for PR'},
            'base': {'type': 'string', 'description': 'Target branch for PR (e.g. main)'},
            'merge_method': {'type': 'string', 'enum': ['merge', 'squash', 'rebase'], 'description': 'Merge method'},
            'delete_branch': {'type': 'boolean', 'description': 'Delete source branch after merge'},
            'release_id': {'type': 'integer', 'description': 'Release ID'},
            'tag': {'type': 'string', 'description': 'Tag name for the release'},
            'release_name': {'type': 'string', 'description': 'Release title'},
            'notes': {'type': 'string', 'description': 'Release notes (create_release, update_release)'},
            'draft': {'type': 'boolean', 'description': 'Whether release is a draft'},
            'prerelease': {'type': 'boolean', 'description': 'Whether release is a prerelease'},
            'attachments': {'type': 'array', 'items': {'type': 'string'}, 'description': 'File paths to attach'},
        }
        return self._build_schema(self._action_names(), props)

    def _keep_issue(self, issue: dict[str, Any]) -> bool:
        return 'pull_request' not in issue

    def _clone_url(self, repo: str) -> str:
        host = urlsplit(self._base_url).netloc or 'github.com'
        if host == 'api.github.com':
            host = 'github.com'
        return f'https://x-access-token:{self._access_token}@{host}/{repo}.git'

    def _create_issue(self, p: dict[str, Any]) -> str:
        repo, title, body, assignee = p.get('repo', ''), p.get('title'), p.get('body'), p.get('assignee')
        err = self._need(repo=repo, title=title)
        if err:
            return err
        payload: dict[str, Any] = {'title': title, 'body': body or ''}
        if assignee:
            payload['assignees'] = [assignee]
        return self._fmt_issue(self._request('POST', f'/repos/{repo}/issues', json=payload))

    def _update_issue(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('issue_number')
        err = self._need(repo=repo, issue_number=num)
        if err:
            return err
        payload: dict[str, Any] = {}
        if p.get('title') is not None:
            payload['title'] = p['title']
        if p.get('body') is not None:
            payload['body'] = p['body']
        if p.get('state') in ('open', 'closed'):
            payload['state'] = p['state']
        if p.get('assignee') is not None:
            payload['assignees'] = [p['assignee']] if p['assignee'] else []
        if not payload:
            return 'Error: nothing to update'
        return self._fmt_issue(self._request('PATCH', f'/repos/{repo}/issues/{num}', json=payload))

    def _create_pull_request(self, p: dict[str, Any]) -> str:
        repo, title, body, head, base, assignee = p.get('repo', ''), p.get('title'), p.get('body'), p.get('head'), p.get('base'), p.get('assignee')
        err = self._need(repo=repo, title=title, head=head, base=base)
        if err:
            return err
        payload: dict[str, Any] = {'title': title, 'head': head, 'base': base, 'body': body or ''}
        data = self._request('POST', f'/repos/{repo}/pulls', json=payload)
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        if assignee:
            self._request('PATCH', f'/repos/{repo}/issues/{data["number"]}', json={'assignees': [assignee]})
        return self._fmt_pr(data)

    def _update_pull_request(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        payload: dict[str, Any] = {}
        if p.get('title') is not None:
            payload['title'] = p['title']
        if p.get('body') is not None:
            payload['body'] = p['body']
        if p.get('state') in ('open', 'closed'):
            payload['state'] = p['state']
        if p.get('assignee') is not None:
            payload['assignees'] = [p['assignee']] if p['assignee'] else []
        if not payload:
            return 'Error: nothing to update'
        return self._fmt_pr(self._request('PATCH', f'/repos/{repo}/pulls/{num}', json=payload))

    def _merge_pull_request(self, p: dict[str, Any]) -> str:
        repo, num, method, delete_branch = p.get('repo', ''), p.get('pr_number'), p.get('merge_method'), p.get('delete_branch')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        payload: dict[str, Any] = {}
        if method:
            payload['merge_method'] = method
        data = self._request('PUT', f'/repos/{repo}/pulls/{num}/merge', json=payload)
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        result = f'Pull request #{num} merged successfully.'
        if delete_branch:
            pr = self._request('GET', f'/repos/{repo}/pulls/{num}')
            head = pr.get('head', {}).get('ref') if isinstance(pr, dict) else None
            if head:
                self._request('DELETE', f'/repos/{repo}/git/refs/heads/{head}')
                result += f' Deleted branch {head}.'
            else:
                result += ' (branch deletion skipped: could not read head ref)'
        return result

    def _close_pull_request(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        return self._fmt_pr(self._request('PATCH', f'/repos/{repo}/pulls/{num}', json={'state': 'closed'}))

    def _list_releases(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        data = self._paginate(f'/repos/{repo}/releases')
        return self._render_list(data, 'Releases:', lambda r: f'{r["tag_name"]}: {r.get("name") or "(untitled)"}{" [DRAFT]" if r.get("draft") else ""}{" [PRE]" if r.get("prerelease") else ""}', 'No releases found.')

    def _get_release(self, p: dict[str, Any]) -> str:
        repo, rid, tag = p.get('repo', ''), p.get('release_id'), p.get('tag')
        err = self._need(repo=repo)
        if err:
            return err
        if not rid and not tag:
            return 'Error: repo and either release_id or tag parameter required'
        if tag:
            data = self._request('GET', f'/repos/{repo}/releases/tags/{tag}')
        else:
            data = self._request('GET', f'/repos/{repo}/releases/{rid}')
        return self._fmt_release(data)

    def _create_release(self, p: dict[str, Any]) -> str:
        repo, tag, name, draft, prerelease, attachments = p.get('repo', ''), p.get('tag'), p.get('release_name'), p.get('draft'), p.get('prerelease'), p.get('attachments')
        notes, body_err, aliased = self._release_notes(p)
        err = self._need(repo=repo, tag=tag) or body_err
        if err:
            return err
        payload: dict[str, Any] = {'tag_name': tag, 'name': name or tag, 'body': notes or '', 'draft': bool(draft), 'prerelease': bool(prerelease)}
        data = self._request('POST', f'/repos/{repo}/releases', json=payload)
        err2 = self._fmt_error(data)
        if err2:
            return err2
        result = self._with_body_note(self._fmt_release(data), aliased)
        if attachments:
            result += '\n\n' + self._upload_attachments(data['upload_url'], [str(a) for a in attachments])
        return result

    def _update_release(self, p: dict[str, Any]) -> str:
        repo, rid = p.get('repo', ''), p.get('release_id')
        notes, body_err, aliased = self._release_notes(p)
        err = self._need(repo=repo, release_id=rid) or body_err
        if err:
            return err
        payload: dict[str, Any] = {}
        if p.get('release_name') is not None:
            payload['name'] = p['release_name']
        if notes is not None:
            payload['body'] = notes
        if p.get('draft') is not None:
            payload['draft'] = p['draft']
        if p.get('prerelease') is not None:
            payload['prerelease'] = p['prerelease']
        if not payload:
            return 'Error: nothing to update'
        return self._with_body_note(self._fmt_release(self._request('PATCH', f'/repos/{repo}/releases/{rid}', json=payload)), aliased)

    def _delete_release(self, p: dict[str, Any]) -> str:
        repo, rid = p.get('repo', ''), p.get('release_id')
        err = self._need(repo=repo, release_id=rid)
        if err:
            return err
        data = self._request('DELETE', f'/repos/{repo}/releases/{rid}')
        return self._fmt_error(data) or f'Release #{rid} deleted successfully.'

    def _upload_attachments(self, upload_url: str, paths: list[str]) -> str:
        results: list[str] = []
        for filepath in paths:
            path = Path(filepath)
            if not path.exists():
                results.append(f'  - {filepath}: file not found, skipped')
                continue
            try:
                with open(path, 'rb') as f:
                    endpoint = upload_url.replace('{?name,label}', '')
                    resp = httpx.post(
                        endpoint, headers={'Authorization': f'Bearer {self._access_token}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/octet-stream'}, params={'name': path.name}, content=f.read(), timeout=60
                    )
                    results.append(f'  - {filepath}: uploaded OK' if resp.status_code == 201 else f'  - {filepath}: upload failed (HTTP {resp.status_code})')
            except Exception as e:
                results.append(f'  - {filepath}: upload error - {e}')
        return 'Attachments:\n' + '\n'.join(results)

    def _fmt_issue(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        labels = ', '.join(lb.get('name', '') for lb in data.get('labels', [])) if data.get('labels') else ''
        assignees = ', '.join(a.get('login', '') for a in data.get('assignees', [])) if data.get('assignees') else ''
        lines = [
            f'Issue #{data.get("number", "?")}: {data.get("title", "")}',
            f'State: {data.get("state", "unknown")}',
            f'Author: {data.get("user", {}).get("login", "unknown")}',
            f'Created: {data.get("created_at", "")}',
            '',
            data.get('body') or '(no description)',
        ]
        if assignees:
            lines.append(f'Assignees: {assignees}')
        if labels:
            lines.append(f'Labels: {labels}')
        return '\n'.join(lines)

    def _fmt_pr(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        assignees = ', '.join(a.get('login', '') for a in data.get('assignees', [])) if data.get('assignees') else ''
        lines = [
            f'PR #{data.get("number", "?")}: {data.get("title", "")}',
            f'State: {data.get("state", "unknown")}',
            f'Author: {data.get("user", {}).get("login", "unknown")}',
            f'Branch: {data.get("head", {}).get("ref", "?")} -> {data.get("base", {}).get("ref", "?")}',
            f'Created: {data.get("created_at", "")}',
            '',
            data.get('body') or '(no description)',
        ]
        if assignees:
            lines.append(f'Assignees: {assignees}')
        if data.get('merged'):
            lines.append(f'Merged: {data.get("merged_at", "yes")}')
        return '\n'.join(lines)

    def _fmt_release(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        draft = ' [DRAFT]' if data.get('draft') else ''
        prerelease = ' [PRE]' if data.get('prerelease') else ''
        lines = [
            f'Release: {data.get("tag_name", "?")}{draft}{prerelease}',
            f'Title: {data.get("name") or "(untitled)"}',
            f'Author: {data.get("author", {}).get("login", "unknown")}',
            f'Created: {data.get("created_at", "")}',
            f'Published: {data.get("published_at", "")}',
            '',
            data.get('body') or '(no release notes)',
        ]
        assets = data.get('assets', [])
        if assets:
            lines.append(f'Attachments ({len(assets)}):')
            lines.extend(f'  - {a.get("name", "?")} ({a.get("size", 0)} bytes)' for a in assets)
        return '\n'.join(lines)
