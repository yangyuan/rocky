from __future__ import annotations

import time
from collections.abc import Iterator

from agents.items import TResponseStreamEvent
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseTextDeltaEvent,
)


class ResponseStreamEmitter:
    def __init__(self, *, response_id: str, model_label: str):
        self._response_id = response_id
        self._model_label = model_label
        self._sequence = 0
        self._accumulated = ""
        self._closed = False
        self._response = Response(
            id=response_id,
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
            id=self._response_id,
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
            item_id=self._response_id,
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
            item_id=self._response_id,
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
            item_id=self._response_id,
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
