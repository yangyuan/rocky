from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Optional

from agents.items import MessageOutputItem, RunItem, ToolCallItem, ToolCallOutputItem
from agents.stream_events import (
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)
from openai.types.responses import (
    ResponseOutputText,
    ResponseTextDeltaEvent,
)
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_output_item import McpCall

from rocky.contracts.agent import (
    RockyAgentStatus,
    RockyChatChunkEvent,
    RockyStreamEvent,
)
from rocky.contracts.chat import RockyChatMessage, RockyToolCall
from rocky.services.messages import RockyMessages

logger = logging.getLogger(__name__)


class RockyStreaming:
    def __init__(self) -> None:
        self._state: Optional[RockyAgentStatus] = None
        self._assistant_text = ""

    async def stream(
        self,
        events: AsyncIterator[StreamEvent],
    ) -> AsyncIterator[RockyStreamEvent]:
        async for event in events:
            if isinstance(event, RawResponsesStreamEvent):
                for item in self._convert_raw_response_stream_event(event):
                    yield item
            elif isinstance(event, RunItemStreamEvent):
                for item in self._convert_run_item_stream_event(event):
                    yield item
        message = self._flush_assistant_message()
        if message is not None:
            yield message

    def _convert_raw_response_stream_event(
        self,
        event: RawResponsesStreamEvent,
    ) -> list[RockyStreamEvent]:
        items: list[RockyStreamEvent] = []
        if isinstance(event.data, ResponseTextDeltaEvent):
            delta = event.data.delta
            if delta:
                self._assistant_text += delta
                stream_event = RockyChatChunkEvent(delta=delta)
                if self._state != RockyAgentStatus.RESPONDING:
                    self._state = RockyAgentStatus.RESPONDING
                    stream_event.state = RockyAgentStatus.RESPONDING
                items.append(stream_event)
                return items
        state_event = self._state_event(RockyAgentStatus.RESPONDING)
        if state_event is not None:
            items.append(state_event)
        return items

    def _convert_run_item_stream_event(
        self,
        event: RunItemStreamEvent,
    ) -> list[RockyStreamEvent]:
        match event.name:
            case "message_output_created":
                return self._convert_message_output_item(event.item)
            case "tool_called":
                return self._convert_tool_call_item(event.item)
            case "tool_output":
                return self._convert_tool_output_item(event.item)
            case "reasoning_item_created":
                return self._convert_reasoning_item()
            case (
                "handoff_requested"
                | "handoff_occured"
                | "tool_search_called"
                | "tool_search_output_created"
                | "mcp_approval_requested"
                | "mcp_approval_response"
                | "mcp_list_tools"
            ):
                return []
            case _:
                logger.warning("Unsupported run item stream event: %s", event.name)
                return []

    def _convert_message_output_item(self, item: RunItem) -> list[RockyStreamEvent]:
        if not isinstance(item, MessageOutputItem):
            logger.warning("Expected message output item, got %s", type(item).__name__)
            return []
        text = self._message_output_text(item) or self._assistant_text
        self._assistant_text = ""
        if not text:
            return []
        items: list[RockyStreamEvent] = []
        state_event = self._state_event(RockyAgentStatus.RESPONDING)
        if state_event is not None:
            items.append(state_event)
        items.append(RockyChatMessage(role=item.raw_item.role, content=text))
        return items

    def _convert_tool_call_item(self, item: RunItem) -> list[RockyStreamEvent]:
        items: list[RockyStreamEvent] = []
        message = self._flush_assistant_message()
        if message is not None:
            items.append(message)
        state_event = self._state_event(RockyAgentStatus.EXECUTING)
        if state_event is not None:
            items.append(state_event)
        tool_call = self._convert_tool_call_item_to_tool_call(item)
        if tool_call is None:
            return items
        items.append(self._assistant_output_message(tool_calls=[tool_call]))
        return items

    def _convert_tool_output_item(self, item: RunItem) -> list[RockyStreamEvent]:
        items: list[RockyStreamEvent] = []
        state_event = self._state_event(RockyAgentStatus.SENDING)
        if state_event is not None:
            items.append(state_event)
        tool_result = self._convert_tool_output_item_to_tool_call(item)
        if tool_result is None:
            return items
        items.append(
            RockyChatMessage(
                role="tool",
                content=RockyMessages.tool_result_to_chat_content(tool_result.output),
                tool_call_id=tool_result.id,
            )
        )
        return items

    def _convert_reasoning_item(self) -> list[RockyStreamEvent]:
        if self._state == RockyAgentStatus.EXECUTING:
            return []
        event = self._state_event(RockyAgentStatus.THINKING)
        return [] if event is None else [event]

    def _state_event(
        self,
        state: RockyAgentStatus,
    ) -> Optional[RockyChatChunkEvent]:
        if self._state == state:
            return None
        self._state = state
        return RockyChatChunkEvent(state=state)

    def _flush_assistant_message(self) -> Optional[RockyChatMessage]:
        if not self._assistant_text:
            return None
        message = self._assistant_output_message(content=self._assistant_text)
        self._assistant_text = ""
        return message

    @staticmethod
    def _assistant_output_message(
        content: str = "",
        tool_calls: Optional[list[RockyToolCall]] = None,
    ) -> RockyChatMessage:
        return RockyChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _message_output_text(item: MessageOutputItem) -> str:
        parts: list[str] = []
        for content in item.raw_item.content:
            if isinstance(content, ResponseOutputText):
                parts.append(content.text)
        return "".join(parts)

    @classmethod
    def _convert_tool_call_item_to_tool_call(
        cls,
        item: RunItem,
    ) -> Optional[RockyToolCall]:
        if not isinstance(item, ToolCallItem):
            logger.warning("Expected tool call item, got %s", type(item).__name__)
            return None
        raw = item.raw_item
        if isinstance(raw, ResponseFunctionToolCall):
            return RockyToolCall(
                id=raw.call_id,
                name=raw.name,
                arguments=cls._convert_tool_arguments(raw.arguments),
            )
        if isinstance(raw, McpCall):
            return RockyToolCall(
                id=raw.id,
                name=raw.name,
                arguments=cls._convert_tool_arguments(raw.arguments),
            )
        if isinstance(raw, dict):
            call_id = raw.get("call_id") or raw.get("id") or ""
            name = raw.get("name") or raw.get("type") or "tool"
            arguments = raw.get("arguments", raw.get("input"))
            return RockyToolCall(
                id=str(call_id),
                name=str(name),
                arguments=cls._convert_tool_arguments(arguments),
            )
        logger.warning("Unsupported tool call raw item: %s", type(raw).__name__)
        return None

    @staticmethod
    def _convert_tool_output_item_to_tool_call(
        item: RunItem,
    ) -> Optional[RockyToolCall]:
        if not isinstance(item, ToolCallOutputItem):
            logger.warning("Expected tool output item, got %s", type(item).__name__)
            return None
        return RockyToolCall(
            id=item.call_id or "",
            output=RockyMessages.to_json_value(item.output),
            completed=True,
        )

    @classmethod
    def _convert_tool_arguments(cls, value: Optional[str | dict]) -> dict | str:
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return value
            if isinstance(decoded, dict):
                return decoded
            return value
        if isinstance(value, dict):
            return value
        return {}
