from __future__ import annotations

import time
from collections.abc import Iterator

from agents.items import TResponseOutputItem, TResponseStreamEvent
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseTextDeltaEvent,
)


class ResponseStreamEmitter:
    def __init__(self, *, event_id: str, model_label: str):
        self._event_id = event_id
        self._model_label = model_label
        self._sequence = 0
        self._accumulated = ""
        self._closed = False
        self._response = Response(
            id=event_id,
            created_at=time.time(),
            model=model_label,
            object="response",
            output=[],
            tool_choice="auto",
            tools=[],
            parallel_tool_calls=False,
        )
        self._in_progress_message = self._make_message(status="in_progress")

    def _next_sequence(self) -> int:
        n = self._sequence
        self._sequence += 1
        return n

    def _make_message(
        self,
        *,
        status: str,
        content: list[ResponseOutputText] | None = None,
    ) -> ResponseOutputMessage:
        return ResponseOutputMessage(
            id=self._event_id,
            content=content or [],
            role="assistant",
            type="message",
            status=status,
        )

    def open(self) -> Iterator[TResponseStreamEvent]:
        text_part = ResponseOutputText(text="", type="output_text", annotations=[])
        yield ResponseCreatedEvent(
            response=self._response,
            type="response.created",
            sequence_number=self._next_sequence(),
        )
        yield ResponseOutputItemAddedEvent(
            item=self._in_progress_message,
            output_index=0,
            type="response.output_item.added",
            sequence_number=self._next_sequence(),
        )
        yield ResponseContentPartAddedEvent(
            content_index=0,
            item_id=self._event_id,
            output_index=0,
            part=text_part,
            type="response.content_part.added",
            sequence_number=self._next_sequence(),
        )

    def text_delta(self, delta: str) -> Iterator[TResponseStreamEvent]:
        if not delta:
            return
        self._accumulated += delta
        yield ResponseTextDeltaEvent(
            content_index=0,
            delta=delta,
            item_id=self._event_id,
            output_index=0,
            type="response.output_text.delta",
            sequence_number=self._next_sequence(),
            logprobs=[],
        )

    def close(self) -> Iterator[TResponseStreamEvent]:
        if self._closed:
            return
        self._closed = True
        final_text = ResponseOutputText(
            text=self._accumulated, type="output_text", annotations=[]
        )
        completed_message = self._make_message(status="completed", content=[final_text])
        yield ResponseContentPartDoneEvent(
            content_index=0,
            item_id=self._event_id,
            output_index=0,
            part=final_text,
            type="response.content_part.done",
            sequence_number=self._next_sequence(),
        )
        yield ResponseOutputItemDoneEvent(
            item=completed_message,
            output_index=0,
            type="response.output_item.done",
            sequence_number=self._next_sequence(),
        )
        final_response = self._response.model_copy()
        final_response.output = [completed_message]
        yield ResponseCompletedEvent(
            response=final_response,
            type="response.completed",
            sequence_number=self._next_sequence(),
        )

    def emit(self, output: list[TResponseOutputItem]) -> Iterator[TResponseStreamEvent]:
        if self._closed:
            return
        self._closed = True
        yield ResponseCreatedEvent(
            response=self._response,
            type="response.created",
            sequence_number=self._next_sequence(),
        )
        for output_index, item in enumerate(output):
            yield from self._emit_output_item(item, output_index=output_index)
        final_response = self._response.model_copy()
        final_response.output = output
        yield ResponseCompletedEvent(
            response=final_response,
            type="response.completed",
            sequence_number=self._next_sequence(),
        )

    def _emit_output_item(
        self, item: TResponseOutputItem, *, output_index: int
    ) -> Iterator[TResponseStreamEvent]:
        added_item = self._added_item(item)
        yield ResponseOutputItemAddedEvent(
            item=added_item,
            output_index=output_index,
            type="response.output_item.added",
            sequence_number=self._next_sequence(),
        )
        if isinstance(item, ResponseFunctionToolCall):
            yield from self._emit_function_call(item, output_index=output_index)
        elif isinstance(item, ResponseOutputMessage):
            yield from self._emit_message(item, output_index=output_index)
        yield ResponseOutputItemDoneEvent(
            item=item,
            output_index=output_index,
            type="response.output_item.done",
            sequence_number=self._next_sequence(),
        )

    def _added_item(self, item: TResponseOutputItem) -> TResponseOutputItem:
        if isinstance(item, ResponseFunctionToolCall):
            return ResponseFunctionToolCall(
                id=item.id,
                call_id=item.call_id,
                arguments="",
                name=item.name,
                type="function_call",
            )
        if isinstance(item, ResponseOutputMessage):
            return ResponseOutputMessage(
                id=item.id,
                content=[],
                role=item.role,
                type=item.type,
                status="in_progress",
            )
        return item

    def _emit_function_call(
        self, item: ResponseFunctionToolCall, *, output_index: int
    ) -> Iterator[TResponseStreamEvent]:
        if item.arguments:
            yield ResponseFunctionCallArgumentsDeltaEvent(
                delta=item.arguments,
                item_id=item.call_id,
                output_index=output_index,
                type="response.function_call_arguments.delta",
                sequence_number=self._next_sequence(),
            )
        yield ResponseFunctionCallArgumentsDoneEvent(
            arguments=item.arguments,
            item_id=item.call_id,
            name=item.name,
            output_index=output_index,
            type="response.function_call_arguments.done",
            sequence_number=self._next_sequence(),
        )

    def _emit_message(
        self, item: ResponseOutputMessage, *, output_index: int
    ) -> Iterator[TResponseStreamEvent]:
        for content_index, part in enumerate(item.content or []):
            if not isinstance(part, ResponseOutputText):
                continue
            yield ResponseContentPartAddedEvent(
                content_index=content_index,
                item_id=item.id,
                output_index=output_index,
                part=ResponseOutputText(
                    text="", type="output_text", annotations=[], logprobs=[]
                ),
                type="response.content_part.added",
                sequence_number=self._next_sequence(),
            )
            if part.text:
                yield ResponseTextDeltaEvent(
                    content_index=content_index,
                    delta=part.text,
                    item_id=item.id,
                    output_index=output_index,
                    type="response.output_text.delta",
                    sequence_number=self._next_sequence(),
                    logprobs=[],
                )
            yield ResponseContentPartDoneEvent(
                content_index=content_index,
                item_id=item.id,
                output_index=output_index,
                part=part,
                type="response.content_part.done",
                sequence_number=self._next_sequence(),
            )
