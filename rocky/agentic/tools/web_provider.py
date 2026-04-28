from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from rocky.agentic.contracts.web import (
    WebError,
    WebFindResults,
    WebPage,
    WebPageMatch,
    WebSearchResult,
    WebSearchResults,
    WebSource,
)

_MAX_SEARCH_RESULTS_PER_QUERY = 5
_MAX_PAGE_CHARS = 40_000
_MAX_MATCHES = 20
_PAGE_FORMAT = "text_markdown"


class WebProvider:
    def search(
        self,
        queries: list[str],
        sources: list[WebSource] | None = None,
    ) -> WebSearchResults | WebError:
        try:
            from ddgs import DDGS
        except ImportError:
            return WebError(
                message="The ddgs package is not installed. Install it with: pip install ddgs"
            )

        results: list[WebSearchResult] = []
        search_client = DDGS()
        try:
            for query in queries:
                for item in search_client.text(
                    query,
                    max_results=_MAX_SEARCH_RESULTS_PER_QUERY,
                ):
                    if isinstance(item, dict):
                        results.append(self._search_result(query, item))
        except Exception as error:
            return WebError(message=f"Web search failed: {error}")

        return WebSearchResults(
            queries=queries,
            sources=self._search_sources(sources or []),
            results=results,
        )

    def open_page(self, url: str) -> WebPage | WebError:
        return self._fetch_page(url)

    def find_in_page(self, url: str, pattern: str) -> WebFindResults | WebError:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as error:
            return WebError(message=f"Invalid find_in_page pattern: {error}")

        page = self._fetch_page(url)
        if isinstance(page, WebError):
            return page
        matches = self._matches(page.text, regex)
        return WebFindResults(
            url=page.url,
            title=page.title,
            pattern=pattern,
            match_count=len(matches),
            matches=matches,
        )

    def _fetch_page(self, url: str) -> WebPage | WebError:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return WebError(message="URL must be an absolute http or https URL.")
        try:
            from ddgs import DDGS
        except ImportError:
            return WebError(
                message="The ddgs package is not installed. Install it with: pip install ddgs"
            )

        try:
            page = DDGS().extract(url, fmt=_PAGE_FORMAT)
        except Exception as error:
            return WebError(message=f"Unable to open page: {error}")

        content = page.get("content") or ""
        text = (
            content.decode(errors="replace")
            if isinstance(content, bytes)
            else str(content)
        )
        text_truncated = len(text) > _MAX_PAGE_CHARS
        return WebPage(
            url=str(page.get("url") or url),
            title=self._markdown_title(text),
            content_type="text/markdown",
            text=text[:_MAX_PAGE_CHARS],
            truncated=text_truncated,
        )

    @staticmethod
    def _markdown_title(text: str) -> str:
        for line in text.splitlines():
            title = line.strip()
            if title.startswith("#"):
                return re.sub(r"\s+", " ", title.lstrip("#")).strip()
        return ""

    def _search_sources(
        self,
        sources: list[WebSource],
    ) -> list[WebSource]:
        has_ddgs = any(
            source.type == "api" and source.name == "ddgs" for source in sources
        )
        if not has_ddgs:
            sources.append(WebSource(type="api", name="ddgs"))
        return sources

    def _search_result(self, query: str, item: dict[str, Any]) -> WebSearchResult:
        return WebSearchResult(
            query=query,
            title=str(item.get("title") or "").strip(),
            url=str(item.get("href") or item.get("url") or "").strip(),
            snippet=str(item.get("body") or item.get("snippet") or "").strip(),
        )

    def _matches(self, text: str, regex: re.Pattern[str]) -> list[WebPageMatch]:
        matches: list[WebPageMatch] = []
        for match in regex.finditer(text):
            start = match.start()
            end = match.end()
            context_start = max(0, start - 160)
            context_end = min(len(text), end + 160)
            matches.append(
                WebPageMatch(
                    text=match.group(0),
                    start=start,
                    end=end,
                    context=text[context_start:context_end].strip(),
                )
            )
            if len(matches) >= _MAX_MATCHES:
                break
        return matches
