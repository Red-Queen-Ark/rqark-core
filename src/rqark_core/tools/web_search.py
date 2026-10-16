import asyncio
from typing import Any

from rqark_core.func.epistemic import KEYWORD_BLACKLIST, URL_BLACKLIST, domain_matches
from rqark_core.types.tool import BaseTool, ToolContext

DDGS: Any = None
try:
    from ddgs import DDGS as _DDGS

    DDGS = _DDGS
except ImportError:
    pass


class WebSearch(BaseTool):
    MAX_RESULTS: int = 10
    SAFESEARCH: str = 'moderate'

    @property
    def name(self) -> str:
        return 'web_search'

    @property
    def display_key(self) -> str:
        return 'query'

    def get_openai_schema(self) -> dict[str, Any]:
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': 'Search the web for current information. Returns a list of results with titles, URLs, and snippets.',
                'parameters': {'type': 'object', 'properties': {'query': {'type': 'string', 'description': 'The search query'}}, 'required': ['query']},
            },
        }

    async def run(self, ctx: ToolContext | None = None, **kwargs: Any) -> str:
        return await asyncio.to_thread(self._search_duckduckgo, kwargs['query'])

    _SAFESEARCH_MAP: dict[str, str] = {'strict': 'on', 'moderate': 'moderate', 'off': 'off'}

    def _search_duckduckgo(self, query: str) -> str:
        if DDGS is None:
            return 'Search failed: DuckDuckGo library not installed'
        try:
            ddgs = DDGS(timeout=10)
            raw = list(ddgs.text(query, max_results=self.MAX_RESULTS, safesearch=self._SAFESEARCH_MAP.get(self.SAFESEARCH, self.SAFESEARCH)))
            if not raw:
                return f'No results for: {query}'
            items = [{'title': r.get('title', ''), 'url': r.get('href', ''), 'description': r.get('body', '')} for r in raw]
            return self._format_results(query, items)
        except Exception as e:
            msg = str(e)
            if 'No results' in msg or 'not found' in msg.lower():
                return f'No results for: {query}'
            return f'Search failed: DuckDuckGo error ({e})'

    def _format_results(self, query: str, results: list[dict[str, Any]]) -> str:
        filtered = [r for r in results if not any(domain_matches(r.get('url', ''), d) for d in URL_BLACKLIST) and not any(kw.lower() in (r.get('title', '') + r.get('description', '')).lower() for kw in KEYWORD_BLACKLIST)]
        if not filtered:
            return 'All results filtered.'
        lines = [f'Results for: {query}\n']
        for i, item in enumerate(filtered[: self.MAX_RESULTS], 1):
            lines.append(f'{i}. {item.get("title", "")}')
            lines.append(f'   {item.get("url", "")}')
            if desc := item.get('description') or item.get('content'):
                lines.append(f'   {desc}')
        return '\n'.join(lines)
