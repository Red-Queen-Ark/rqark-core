import platform
import re
from html import unescape
from typing import Any
import httpx
from rqark_core.types.tool import BaseTool
from rqark_core.func.epistemic import grade_source


class WebFetch(BaseTool):
    PROXY: str | None = None
    catalog_group: str = 'read'

    @property
    def name(self) -> str:
        return 'web_fetch'

    @property
    def display_key(self) -> str:
        return 'url'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Fetch the content of a URL and return it as plain text. Use for reading articles, documentation, or any web page.',
                'parameters': {'type': 'object', 'properties': {'url': {'type': 'string', 'description': 'The URL to fetch'}}, 'required': ['url']},
            },
        }

    @staticmethod
    def _user_agent() -> str:
        system = platform.system()
        if system == 'Windows':
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        if system == 'Linux':
            return 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    @staticmethod
    def _clean_html(text: str, max_lines: int = 200) -> str:
        """Strip scripts, styles, and tags from HTML, returning plain text."""
        text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
        text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
        text = re.sub(r'<[^>]+>', '', text)
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        return '\n'.join(lines[:max_lines])

    def _build_response(self, url: str, content: str) -> str:
        grade = grade_source(url)
        parts = []

        if grade is None:
            parts.append('Score: — (unclassified)')
        else:
            tier, label = grade
            parts.append(f'Score: {tier} — {label}')
            if tier == 0:
                parts.append(f'Epistemic Warning: {url} — Untrusted')

        parts.append(f'--- Raw Content ---\n{content}')
        return '\n\n'.join(parts)

    def run(self, **kwargs: Any) -> str:
        url = kwargs['url']
        headers = {'User-Agent': self._user_agent()}
        try:
            with httpx.Client(proxy=self.PROXY, follow_redirects=True, timeout=30) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                content_type = resp.headers.get('content-type', '')
                if 'text/html' in content_type:
                    content = self._clean_html(resp.text)
                else:
                    content = resp.text[:10000]
        except httpx.HTTPStatusError as e:
            return f'Fetch failed: HTTP {e.response.status_code}'
        except httpx.RequestError as e:
            return f'Fetch failed: {e}'
        return self._build_response(url, content)

    async def run_async(self, **kwargs: Any) -> str:
        url = kwargs['url']
        headers = {'User-Agent': self._user_agent()}
        try:
            async with httpx.AsyncClient(proxy=self.PROXY, follow_redirects=True, timeout=30) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                content_type = resp.headers.get('content-type', '')
                if 'text/html' in content_type:
                    content = self._clean_html(resp.text)
                else:
                    content = resp.text[:10000]
        except httpx.HTTPStatusError as e:
            return f'Fetch failed: HTTP {e.response.status_code}'
        except httpx.RequestError as e:
            return f'Fetch failed: {e}'
        return self._build_response(url, content)
