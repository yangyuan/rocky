from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel


class WebSource(BaseModel):
    type: Literal["url", "api"]
    url: str = ""
    name: str = ""


class WebSearchResult(BaseModel):
    query: str
    title: str
    url: str
    snippet: str


class WebSearchResults(BaseModel):
    type: Literal["search_results"] = "search_results"
    queries: list[str]
    sources: list[WebSource]
    results: list[WebSearchResult]


class WebPage(BaseModel):
    type: Literal["page"] = "page"
    url: str
    title: str
    content_type: str
    text: str
    truncated: bool


class WebPageMatch(BaseModel):
    text: str
    start: int
    end: int
    context: str


class WebError(BaseModel):
    type: Literal["error"] = "error"
    message: str


class WebFindResults(BaseModel):
    type: Literal["find_results"] = "find_results"
    url: str
    title: str
    pattern: str
    match_count: int
    matches: list[WebPageMatch]


WebProviderOutput = Union[WebSearchResults, WebPage, WebFindResults, WebError]
