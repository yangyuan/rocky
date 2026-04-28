from __future__ import annotations

from typing import Any

from rocky.agentic.contracts.message import MessageContentText
from rocky.agentic.contracts.tools import (
    FunctionDefinition,
    JsonSchema,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from rocky.agentic.contracts.web import WebError, WebProviderOutput, WebSource
from rocky.agentic.tools.tool import Tool
from rocky.agentic.tools.web_provider import WebProvider

_SOURCE_SCHEMA = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "enum": ["url", "api"],
            "description": "The source type: `url` for a referenced page or `api` for a search provider.",
        },
        "url": {"type": "string", "description": "A referenced web page URL."},
        "name": {
            "type": "string",
            "description": "The search provider name, such as ddgs.",
        },
    },
    "description": "A source used or referenced by a web action.",
}


WEB_SEARCH_ACTION_SCHEMA = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "enum": ["search", "open_page", "find_in_page"],
            "description": (
                "Use `search` to discover pages, `open_page` to read a known URL, "
                "or `find_in_page` to locate text within a known URL."
            ),
            "default": "search",
        },
        "query": {
            "type": "string",
            "description": "A web search query. Required for `search` unless `queries` is provided.",
        },
        "queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Multiple web search queries to run in one `search` action.",
        },
        "sources": {
            "type": "array",
            "items": _SOURCE_SCHEMA,
            "description": "Sources already consulted or referenced by the action.",
        },
        "url": {
            "type": "string",
            "description": "The absolute http or https URL for `open_page` or `find_in_page`.",
        },
        "pattern": {
            "type": "string",
            "description": "A regular expression to find within the fetched page text.",
        },
    },
    "description": "A web action request for search, page reading, or page text matching.",
}


WEB_TOOL_DEFINITION = ToolDefinition(
    name="web",
    description="Search the web, read known URLs as markdown, and find text within fetched pages.",
    channel="commentary",
    unconstrained=True,
    functions=[
        FunctionDefinition(
            name="search",
            description="Run a web action: search for pages, open a known URL, or find text within a known URL.",
            parameters=JsonSchema.model_validate(WEB_SEARCH_ACTION_SCHEMA),
            strict=False,
        )
    ],
)


class WebTool(Tool):
    def __init__(self, provider: WebProvider | None = None) -> None:
        super().__init__("web")
        self.provider = provider or WebProvider()
        self.register_callback("search", self.handle_search)

    def get_tool_definition(self) -> ToolDefinition:
        return WEB_TOOL_DEFINITION

    def handle_search(self, tool_call: ToolCall) -> ToolResult:
        arguments = tool_call.arguments
        if not isinstance(arguments, dict):
            return self._error(tool_call, "Web tool arguments must be an object.")
        action_type = arguments.get("type")
        if action_type == "search":
            return self._handle_search(tool_call, arguments)
        if action_type == "open_page":
            return self._handle_open_page(tool_call, arguments)
        if action_type == "find_in_page":
            return self._handle_find_in_page(tool_call, arguments)
        return self._error(
            tool_call,
            "Missing or unsupported web action type. Use search, open_page, or find_in_page.",
        )

    def _handle_search(
        self,
        tool_call: ToolCall,
        arguments: dict[str, Any],
    ) -> ToolResult:
        queries = self._queries(arguments)
        if not queries:
            return self._error(tool_call, "Missing required argument: query or queries")
        return self._provider_result(
            tool_call,
            self.provider.search(queries, self._sources(arguments)),
        )

    def _handle_open_page(
        self,
        tool_call: ToolCall,
        arguments: dict[str, Any],
    ) -> ToolResult:
        url = self._required_string(arguments, "url")
        if url is None:
            return self._error(tool_call, "Missing required argument: url")
        return self._provider_result(tool_call, self.provider.open_page(url))

    def _handle_find_in_page(
        self,
        tool_call: ToolCall,
        arguments: dict[str, Any],
    ) -> ToolResult:
        url = self._required_string(arguments, "url")
        pattern = self._required_string(arguments, "pattern")
        if url is None:
            return self._error(tool_call, "Missing required argument: url")
        if pattern is None:
            return self._error(tool_call, "Missing required argument: pattern")
        return self._provider_result(
            tool_call, self.provider.find_in_page(url, pattern)
        )

    def _queries(self, arguments: dict[str, Any]) -> list[str]:
        raw_queries: list[Any] = []
        query = arguments.get("query")
        if query is not None:
            raw_queries.append(query)
        queries = arguments.get("queries")
        if isinstance(queries, list):
            raw_queries.extend(queries)
        result: list[str] = []
        seen: set[str] = set()
        for raw_query in raw_queries:
            if not isinstance(raw_query, str):
                continue
            normalized = raw_query.strip()
            if normalized and normalized not in seen:
                result.append(normalized)
                seen.add(normalized)
        return result

    def _sources(self, arguments: dict[str, Any]) -> list[WebSource]:
        sources = arguments.get("sources")
        if not isinstance(sources, list):
            return []
        normalized: list[WebSource] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            source_type = source.get("type")
            if source_type == "url" and isinstance(source.get("url"), str):
                normalized.append(WebSource(type="url", url=source["url"]))
            elif source_type == "api" and isinstance(source.get("name"), str):
                normalized.append(WebSource(type="api", name=source["name"]))
        return normalized

    def _required_string(self, arguments: dict[str, Any], name: str) -> str | None:
        value = arguments.get(name)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    def _provider_result(
        self,
        tool_call: ToolCall,
        output: WebProviderOutput,
    ) -> ToolResult:
        return ToolResult(call_id=tool_call.id, output=[self._message(output)])

    def _error(self, tool_call: ToolCall, message: str) -> ToolResult:
        return ToolResult(
            call_id=tool_call.id,
            output=[self._message(WebError(message=message))],
        )

    @staticmethod
    def _message(output: WebProviderOutput) -> MessageContentText:
        return MessageContentText(text=output.model_dump_json())


AGENTIC_TOOL = WebTool
