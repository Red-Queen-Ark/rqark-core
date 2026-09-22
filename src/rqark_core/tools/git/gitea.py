import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from rqark_core.tools.git.base_git import BaseGitTool


class Gitea(BaseGitTool):
    platform_name = 'Gitea'
    api_path_prefix = '/api/v1'
    api_description = 'Interact with Gitea: list/clone repos, manage issues, PRs, milestones, labels, branches, commits, and releases.'
    page_size_param = 'limit'
    max_page_size = 50
    auth_token_prefix = 'token '
    extra_headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    default_base_url = 'https://gitea.com'

    @property
    def name(self) -> str:
        return 'gitea'

    def _action_names(self) -> list[str]:
        return ['list_repos', 'clone_repo', 'list_issues', 'list_prs', 'get_issue', 'create_issue', 'update_issue', 'add_comment', 'set_issue_labels', 'list_milestones', 'list_labels', 'list_branches', 'create_branch', 'delete_branch', 'list_commits', 'compare', 'get_pull_request', 'create_pull_request', 'update_pull_request', 'merge_pull_request', 'close_pull_request', 'list_pull_request_comments', 'add_pull_request_comment', 'list_releases', 'get_release', 'create_release', 'update_release', 'delete_release']

    def get_openai_schema(self) -> dict[str, Any]:
        props = {
            'repo': {'type': 'string', 'description': 'Repository (owner/repo format)'},
            'issue_number': {'type': 'integer', 'description': 'Issue number'},
            'state': {'type': 'string', 'enum': ['open', 'closed', 'all'], 'description': 'Filter by state'},
            'title': {'type': 'string', 'description': 'Title for issue/PR/release'},
            'body': {'type': 'string', 'description': 'Body text for issue/PR/comment/release notes'},
            'assignee': {'type': 'string', 'description': 'Username to assign'},
            'labels': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'Label IDs (see list_labels; set_issue_labels also accepts names)'},
            'milestone': {'type': 'integer', 'description': 'Milestone ID (see list_milestones)'},
            'due_date': {'type': 'string', 'description': 'Due date in ISO 8601 format'},
            'pr_number': {'type': 'integer', 'description': 'Pull request number'},
            'head': {'type': 'string', 'description': 'Source branch for PR'},
            'base': {'type': 'string', 'description': 'Target branch for PR (e.g. main)'},
            'merge_method': {'type': 'string', 'enum': ['merge', 'rebase', 'rebase-merge', 'squash', 'fast-forward-only'], 'description': 'Merge method'},
            'delete_branch': {'type': 'boolean', 'description': 'Delete source branch after merge'},
            'force_merge': {'type': 'boolean', 'description': 'Merge even if required checks have not passed'},
            'release_id': {'type': 'integer', 'description': 'Release ID'},
            'tag': {'type': 'string', 'description': 'Tag name for the release'},
            'release_name': {'type': 'string', 'description': 'Release title'},
            'notes': {'type': 'string', 'description': 'Release notes'},
            'draft': {'type': 'boolean', 'description': 'Whether release is a draft'},
            'prerelease': {'type': 'boolean', 'description': 'Whether release is a prerelease'},
            'attachments': {'type': 'array', 'items': {'type': 'string'}, 'description': 'File paths to attach'},
            'branch': {'type': 'string', 'description': 'Branch name'},
            'from_ref': {'type': 'string', 'description': 'Source ref for compare or create_branch'},
            'to_ref': {'type': 'string', 'description': 'Target ref for compare'},
            'ref_name': {'type': 'string', 'description': 'Branch, tag or SHA to list commits from'},
            'per_page': {'type': 'integer', 'description': 'Number of commits to list (max 50)'},
            'since': {'type': 'string', 'description': 'Only commits after this ISO 8601 date'},
            'until': {'type': 'string', 'description': 'Only commits before this ISO 8601 date'},
        }
        return self._build_schema(self._action_names(), props)

    def _issues_params(self, state: str) -> dict[str, Any]:
        return {'state': state, 'type': 'issues'}

    def _clone_url(self, repo: str) -> str:
        host = urlsplit(self._base_url).netloc or 'gitea.com'
        if not self._username:
            raise ValueError('Gitea username not configured (pass username in params)')
        return f'https://{self._username}:{self._access_token}@{host}/{repo}.git'

    def _optional(self, p: dict[str, Any], payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        for key in keys:
            if p.get(key) is not None:
                payload[key] = p[key]
        return payload

    def _create_issue(self, p: dict[str, Any]) -> str:
        repo, title, body, assignee = p.get('repo', ''), p.get('title'), p.get('body'), p.get('assignee')
        err = self._need(repo=repo, title=title)
        if err:
            return err
        payload: dict[str, Any] = {'title': title}
        if body:
            payload['body'] = body
        if assignee:
            payload['assignees'] = [assignee]
        self._optional(p, payload, ('labels', 'milestone', 'due_date'))
        return self._fmt_issue(self._request('POST', f'/repos/{repo}/issues', json=payload))

    def _update_issue(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('issue_number')
        err = self._need(repo=repo, issue_number=num)
        if err:
            return err
        payload: dict[str, Any] = {}
        self._optional(p, payload, ('title', 'body', 'state', 'milestone', 'due_date'))
        if p.get('assignee') is not None:
            payload['assignees'] = [p['assignee']] if p['assignee'] else []
        if not payload:
            return 'Error: nothing to update'
        return self._fmt_issue(self._request('PATCH', f'/repos/{repo}/issues/{num}', json=payload))

    def _set_issue_labels(self, p: dict[str, Any]) -> str:
        repo, num, labels = p.get('repo', ''), p.get('issue_number'), p.get('labels')
        err = self._need(repo=repo, issue_number=num, labels=labels)
        if err:
            return err
        data = self._request('PUT', f'/repos/{repo}/issues/{num}/labels', json={'labels': labels})
        err2 = self._fmt_error(data)
        if err2:
            return err2
        names = ', '.join(lb.get('name', '?') if isinstance(lb, dict) else str(lb) for lb in data or [])
        return f'Labels on issue #{num} set to: {names or "(none)"}'

    def _create_pull_request(self, p: dict[str, Any]) -> str:
        repo, title, body, head, base, assignee = p.get('repo', ''), p.get('title'), p.get('body'), p.get('head'), p.get('base'), p.get('assignee')
        err = self._need(repo=repo, title=title, head=head, base=base)
        if err:
            return err
        payload: dict[str, Any] = {'title': title, 'head': head, 'base': base}
        if body:
            payload['body'] = body
        if assignee:
            payload['assignees'] = [assignee]
        self._optional(p, payload, ('labels', 'milestone', 'due_date'))
        return self._fmt_pr(self._request('POST', f'/repos/{repo}/pulls', json=payload))

    def _update_pull_request(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        payload: dict[str, Any] = {}
        self._optional(p, payload, ('title', 'body', 'state', 'labels', 'milestone', 'due_date'))
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
            payload['do'] = method
        if delete_branch is not None:
            payload['delete_branch_after_merge'] = delete_branch
        if p.get('force_merge') is not None:
            payload['force_merge'] = p['force_merge']
        data = self._request('POST', f'/repos/{repo}/pulls/{num}/merge', json=payload)
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        return f'Pull request #{num} merged successfully.'

    def _close_pull_request(self, p: dict[str, Any]) -> str:
        repo, num = p.get('repo', ''), p.get('pr_number')
        err = self._need(repo=repo, pr_number=num)
        if err:
            return err
        return self._fmt_pr(self._request('PATCH', f'/repos/{repo}/pulls/{num}', json={'state': 'closed'}))

    def _list_milestones(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        data = self._paginate(f'/repos/{repo}/milestones', params={'state': p.get('state') or 'all'})
        return self._render_list(data, 'Milestones:', lambda m: f'{m["id"]}: {m["title"]} [{m["state"]}]', 'No milestones found.')

    def _list_labels(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        data = self._paginate(f'/repos/{repo}/labels')
        return self._render_list(data, 'Labels:', lambda lb: f'{lb["id"]}: {lb["name"]} (#{lb.get("color", "")})' + (f' - {lb["description"]}' if lb.get('description') else ''), 'No labels found.')

    def _create_branch(self, p: dict[str, Any]) -> str:
        repo, branch = p.get('repo', ''), p.get('branch')
        err = self._need(repo=repo, branch=branch)
        if err:
            return err
        payload: dict[str, Any] = {'new_branch_name': branch}
        if p.get('from_ref'):
            payload['old_ref_name'] = p['from_ref']
        data = self._request('POST', f'/repos/{repo}/branches', json=payload)
        err2 = self._fmt_error(data)
        if err2:
            return err2
        return f'Branch {branch} created.'

    def _delete_branch(self, p: dict[str, Any]) -> str:
        repo, branch = p.get('repo', ''), p.get('branch')
        err = self._need(repo=repo, branch=branch)
        if err:
            return err
        data = self._request('DELETE', f'/repos/{repo}/branches/{branch}')
        return self._fmt_error(data) or f'Branch {branch} deleted.'

    def _fmt_commit(self, c: dict[str, Any]) -> str:
        info = c.get('commit') or {}
        author = info.get('author') or {}
        message = (info.get('message') or '(no message)').splitlines()[0][:80]
        return f'{c.get("sha", "?")[:7]} | {(author.get("date") or "?")[:10]} | {author.get("name") or "unknown"} | {message}'

    def _list_commits(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        per_page = min(int(p.get('per_page') or 20), self.max_page_size)
        params: dict[str, Any] = {}
        if p.get('ref_name'):
            params['sha'] = p['ref_name']
        if p.get('since'):
            params['since'] = p['since']
        if p.get('until'):
            params['until'] = p['until']
        data = self._paginate(f'/repos/{repo}/commits', params=params, limit=per_page)
        return self._render_list(data, 'Commits:', lambda c: self._fmt_commit(c), 'No commits found.')

    def _compare(self, p: dict[str, Any]) -> str:
        repo, frm, to = p.get('repo', ''), p.get('from_ref'), p.get('to_ref')
        err = self._need(repo=repo, from_ref=frm, to_ref=to)
        if err:
            return err
        data = self._request('GET', f'/repos/{repo}/compare/{frm}...{to}')
        err2 = self._fmt_error(data)
        if err2:
            return err2
        commits = data.get('commits') or []
        lines = [f'Compare: {frm}...{to}', f'Commits ({data.get("total_commits", len(commits))}):']
        lines += [f'- {self._fmt_commit(c)}' for c in commits[:30]]
        return '\n'.join(lines)

    def _list_releases(self, p: dict[str, Any]) -> str:
        repo = p.get('repo', '')
        err = self._need(repo=repo)
        if err:
            return err
        data = self._paginate(f'/repos/{repo}/releases', limit=50)
        return self._render_list(data, 'Releases:', lambda r: f'{r.get("tag_name", "?")}: {r.get("name") or "(untitled)"}{" [DRAFT]" if r.get("draft") else ""}{" [PRE]" if r.get("prerelease") else ""}', 'No releases found.')

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
        repo, tag, name, notes, draft, prerelease, attachments = p.get('repo', ''), p.get('tag'), p.get('release_name'), p.get('notes'), p.get('draft'), p.get('prerelease'), p.get('attachments')
        err = self._need(repo=repo, tag=tag)
        if err:
            return err
        payload: dict[str, Any] = {'tag_name': tag}
        if name:
            payload['name'] = name
        if notes:
            payload['body'] = notes
        if draft is not None:
            payload['draft'] = draft
        if prerelease is not None:
            payload['prerelease'] = prerelease
        data = self._request('POST', f'/repos/{repo}/releases', json=payload)
        err2 = self._fmt_error(data)
        if err2:
            return err2
        result = self._fmt_release(data)
        if attachments:
            release_id = data.get('id')
            if release_id:
                result += '\n\n' + self._upload_attachments(repo, release_id, [str(a) for a in attachments])
        return result

    def _update_release(self, p: dict[str, Any]) -> str:
        repo, rid, tag = p.get('repo', ''), p.get('release_id'), p.get('tag')
        err = self._need(repo=repo)
        if err:
            return err
        if not rid and not tag:
            return 'Error: repo and either release_id or tag parameter required'
        payload: dict[str, Any] = {}
        if p.get('release_name') is not None:
            payload['name'] = p['release_name']
        if p.get('notes') is not None:
            payload['body'] = p['notes']
        if p.get('draft') is not None:
            payload['draft'] = p['draft']
        if p.get('prerelease') is not None:
            payload['prerelease'] = p['prerelease']
        if not payload:
            return 'Error: nothing to update'
        if tag:
            rel = self._request('GET', f'/repos/{repo}/releases/tags/{tag}')
            err2 = self._fmt_error(rel)
            if err2:
                return err2
            rid = rel['id']
        return self._fmt_release(self._request('PATCH', f'/repos/{repo}/releases/{rid}', json=payload))

    def _delete_release(self, p: dict[str, Any]) -> str:
        repo, rid, tag = p.get('repo', ''), p.get('release_id'), p.get('tag')
        err = self._need(repo=repo)
        if err:
            return err
        if not rid and not tag:
            return 'Error: repo and either release_id or tag parameter required'
        lookup = f'tags/{tag}' if tag else str(rid)
        data = self._request('DELETE', f'/repos/{repo}/releases/{lookup}')
        return self._fmt_error(data) or f'Release {"tag=" + tag if tag else "#" + str(rid)} deleted successfully.'

    def _upload_attachments(self, repo: str, release_id: int, paths: list[str]) -> str:
        results: list[str] = []
        for filepath in paths:
            path = Path(filepath)
            if not path.exists():
                results.append(f'  - {filepath}: file not found, skipped')
                continue
            mime, _ = mimetypes.guess_type(str(path))
            url = f'{self._base_url}{self.api_path_prefix}/repos/{repo}/releases/{release_id}/assets'
            try:
                with open(path, 'rb') as f:
                    resp = httpx.post(url, headers=self._headers(), files={'attachment': (path.name, f, mime or 'application/octet-stream')}, params={'name': path.name}, timeout=60)
                    results.append(f'  - {filepath}: uploaded OK' if resp.status_code == 201 else f'  - {filepath}: upload failed (HTTP {resp.status_code})')
            except Exception as e:
                results.append(f'  - {filepath}: upload error - {e}')
        return 'Attachments:\n' + '\n'.join(results)

    def _fmt_issue(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        lines = [f'Issue #{data.get("number", "?")}: {data.get("title", "")}', f'State: {data.get("state", "unknown")}', f'Author: {data.get("user", {}).get("login", "unknown")}', f'Created: {data.get("created_at", "unknown")}', '', data.get('body', '(no description)') or '(no description)']
        assignees = data.get('assignees') or []
        if assignees:
            lines.append(f'Assignees: {", ".join(a.get("login", "") for a in assignees)}')
        labels = data.get('labels') or []
        if labels:
            lines.append(f'Labels: {", ".join(lb.get("name", "") for lb in labels)}')
        if data.get('milestone'):
            lines.append(f'Milestone: {data["milestone"].get("title", "?")}')
        if data.get('due_date'):
            lines.append(f'Due: {data["due_date"]}')
        return '\n'.join(lines)

    def _fmt_pr(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        lines = [f'PR #{data.get("number", "?")}: {data.get("title", "")}', f'State: {data.get("state", "unknown")}{" [DRAFT]" if data.get("draft") else ""}', f'Author: {data.get("user", {}).get("login", "unknown")}', f'Branch: {data.get("head", {}).get("ref", "?")} -> {data.get("base", {}).get("ref", "?")}', f'Created: {data.get("created_at", "unknown")}', '', data.get('body', '(no description)') or '(no description)']
        assignees = data.get('assignees') or []
        if assignees:
            lines.append(f'Assignees: {", ".join(a.get("login", "") for a in assignees)}')
        labels = data.get('labels') or []
        if labels:
            lines.append(f'Labels: {", ".join(lb.get("name", "") for lb in labels)}')
        if data.get('milestone'):
            lines.append(f'Milestone: {data["milestone"].get("title", "?")}')
        if data.get('mergeable') is not None:
            lines.append(f'Mergeable: {data["mergeable"]}')
        if data.get('changed_files') is not None:
            lines.append(f'Changes: {data["changed_files"]} files, +{data.get("additions", 0)} -{data.get("deletions", 0)}')
        if data.get('merged'):
            lines.append(f'Merged: {data.get("merged_at", "yes")}')
        return '\n'.join(lines)

    def _fmt_release(self, data: Any) -> str:
        if isinstance(data, dict) and 'error' in data:
            return f'Error: {data["error"]}'
        draft = ' [DRAFT]' if data.get('draft') else ''
        prerelease = ' [PRE]' if data.get('prerelease') else ''
        lines = [f'Release: {data.get("tag_name", "?")}{draft}{prerelease}', f'Title: {data.get("name") or "(untitled)"}', f'Author: {data.get("author", {}).get("login", "unknown")}', f'Created: {data.get("created_at", "unknown")}', f'Published: {data.get("published_at", "unknown")}', '', data.get('body', '(no release notes)') or '(no release notes)']
        assets = data.get('assets') or []
        if assets:
            lines.append(f'Attachments ({len(assets)}):')
            lines.extend(f'  - {a.get("name", "?")} ({a.get("size", 0)} bytes)' for a in assets)
        return '\n'.join(lines)
