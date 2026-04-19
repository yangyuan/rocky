from __future__ import annotations

import asyncio
import logging
import os
import traceback
from collections.abc import AsyncIterator
from typing import Any

from agents.items import ModelResponse, TResponseInputItem, TResponseStreamEvent
from agents.models.interface import Model, ModelTracing
from agents.usage import Usage
from openai.types.responses import ResponseOutputMessage, ResponseOutputText

from rocky.models.providers.messages import (
    LocalMessageBuilder,
    LocalMessageBundle,
    LocalMessageLogSummary,
    new_response_id,
)
from rocky.models.providers.streaming import ResponseStreamEmitter

logger = logging.getLogger("rocky.litertlm")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[litertlm] %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False


os.environ.setdefault("LLVM_PROFILE_FILE", os.devnull)
import litert_lm  # noqa: E402

litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)


class LiteRtLmEngineCache:
    _engines: dict[tuple[str, bool], Any] = {}

    @classmethod
    def get(cls, *, model_path: str, vision: bool) -> Any:
        key = (model_path, vision)
        engine = cls._engines.get(key)
        if engine is None:
            kwargs: dict[str, Any] = {}
            if vision:
                kwargs["vision_backend"] = litert_lm.Backend.CPU
            engine = litert_lm.Engine(model_path, **kwargs)
            cls._engines[key] = engine
        return engine


class LiteRtLmModel(Model):
    def __init__(self, model_path: str):
        if not model_path:
            raise ValueError("model_path is required for LiteRtLmModel")
        self._model_path = model_path
        LiteRtLmEngineCache.get(model_path=model_path, vision=False)

    @property
    def model_path(self) -> str:
        return self._model_path

    @property
    def model_label(self) -> str:
        return f"litert-lm:{self._model_path}"

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> ModelResponse:
        with LocalMessageBuilder.build(
            system_instructions=system_instructions, items=input
        ) as bundle:
            self._prepare(bundle, label="get_response")
            engine = self._engine(bundle)
            history, current = bundle.messages[:-1], bundle.messages[-1]
            kwargs = {"messages": history} if history else {}
            try:
                with engine.create_conversation(**kwargs) as conversation:
                    chunk = conversation.send_message(current)
            except BaseException:
                logger.error(
                    "get_response failed (vision=%s):\n%s",
                    bundle.has_images,
                    traceback.format_exc(),
                )
                raise
        return self._build_response(text=self._extract_text(chunk))

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> AsyncIterator[TResponseStreamEvent]:
        with LocalMessageBuilder.build(
            system_instructions=system_instructions, items=input
        ) as bundle:
            self._prepare(bundle, label="stream_response")
            emitter = ResponseStreamEmitter(
                response_id=new_response_id("litertlm-"),
                model_label=self.model_label,
            )
            for event in emitter.open():
                yield event
            await asyncio.sleep(0)
            engine = self._engine(bundle)
            history, current = bundle.messages[:-1], bundle.messages[-1]
            kwargs = {"messages": history} if history else {}
            with engine.create_conversation(**kwargs) as conversation:
                for chunk in conversation.send_message_async(current):
                    delta = self._extract_text(chunk)
                    if not delta:
                        continue
                    for event in emitter.text_delta(delta):
                        yield event
                    await asyncio.sleep(0)
            for event in emitter.close():
                yield event

    def _prepare(self, bundle: LocalMessageBundle, *, label: str) -> None:
        bundle.replace_history_images("[image attached in earlier turn]")
        logger.info(
            "%s: vision=%s msgs=%d | %s",
            label,
            bundle.has_images,
            len(bundle.messages),
            LocalMessageLogSummary.format(bundle.messages),
        )

    def _build_response(self, *, text: str) -> ModelResponse:
        message = ResponseOutputMessage(
            id=new_response_id("litertlm-"),
            content=[ResponseOutputText(text=text, type="output_text", annotations=[])],
            role="assistant",
            type="message",
            status="completed",
        )
        return ModelResponse(
            output=[message], usage=Usage(requests=1), response_id=None
        )

    def _engine(self, bundle: LocalMessageBundle) -> Any:
        return LiteRtLmEngineCache.get(
            model_path=self._model_path, vision=bundle.has_images
        )

    @staticmethod
    def _extract_text(chunk: Any) -> str:
        parts: list[str] = []
        for item in (chunk or {}).get("content", []) or []:
            if item.get("type") == "text":
                text = item.get("text") or ""
                if text:
                    parts.append(text)
        return "".join(parts)
