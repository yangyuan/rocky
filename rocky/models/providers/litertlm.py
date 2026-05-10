from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import traceback
import uuid
from collections.abc import AsyncIterator, Iterable
from typing import Any

from pydantic import TypeAdapter
from agents.items import (
    ItemHelpers,
    ModelResponse,
    TResponseInputItem,
    TResponseStreamEvent,
)
from agents.models.interface import Model, ModelTracing
from agents.tool import FunctionTool, Tool
from agents.usage import Usage
from openai.types.responses import (
    EasyInputMessage,
    ResponseFunctionToolCall,
    ResponseInputAudio,
    ResponseInputFile,
    ResponseInputFileContent,
    ResponseInputImage,
    ResponseInputImageContent,
    ResponseInputItem,
    ResponseInputText,
    ResponseInputTextContent,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
)
from openai.types.responses.response_function_tool_call_output_item import (
    OutputOutputContentList as ResponseFunctionCallOutputContent,
)
from openai.types.responses.response_input_content import ResponseInputContent
from openai.types.responses.response_input_item import (
    FunctionCallOutput,
    Message,
)
from openai.types.responses.response_output_message import (
    Content as ResponseOutputMessageContent,
)

from rocky.models.providers.streaming import ResponseStreamEmitter
from rocky.services.messages import RockyMessages

logger = logging.getLogger(__name__)


os.environ.setdefault("LLVM_PROFILE_FILE", os.devnull)
import litert_lm

litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)

_RESPONSE_INPUT_ITEM_ADAPTER = TypeAdapter(ResponseInputItem)
_HISTORY_MULTIMODAL_PLACEHOLDER = "[multimodal content from earlier turn]"
LITERTLM_KEEP_VISION_IF_HISTORY_HAS_IMAGES = True


def new_litertlm_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"


class LitertLmEngineCache:
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


class LitertLmToolDeclaration(litert_lm.Tool):
    def __init__(self, tool: FunctionTool):
        self._tool = tool

    def get_tool_description(self) -> dict[str, Any]:
        parameters = self._tool.params_json_schema
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": self._tool.name,
                "description": self._tool.description or "",
                "parameters": parameters,
            },
        }

    def execute(self, param: dict[str, Any]) -> Any:
        raise RuntimeError("LiteRT-LM automatic tool execution is disabled")


class LitertLmMessages:
    @classmethod
    def from_agents_tools(cls, tools: list[Tool]) -> list[Any]:
        converted: list[Any] = []
        for tool in tools:
            if isinstance(tool, FunctionTool):
                converted.append(LitertLmToolDeclaration(tool))
            else:
                logger.warning(
                    "LiteRT-LM only supports function tool declarations; skipping %s",
                    type(tool).__name__,
                )
        return converted

    @classmethod
    def from_agents_input_items(
        cls,
        items: list[ResponseInputItem],
    ) -> list[dict[str, object]]:
        messages: list[dict[str, object]] = []
        tool_names_by_call_id: dict[str, str] = {}
        pending_assistant: dict[str, object] | None = None
        pending_tool_calls: list[dict[str, object]] | None = None

        def flush_assistant() -> None:
            nonlocal pending_assistant, pending_tool_calls
            if pending_assistant is None:
                return
            if not pending_tool_calls:
                pending_assistant.pop("tool_calls", None)
            messages.append(pending_assistant)
            pending_assistant = None
            pending_tool_calls = None

        for item in items:
            if isinstance(item, ResponseFunctionToolCall):
                if pending_assistant is None:
                    pending_tool_calls = []
                    pending_assistant = {
                        "role": "assistant",
                        "content": [],
                        "tool_calls": pending_tool_calls,
                    }
                elif pending_tool_calls is None:
                    pending_tool_calls = []
                    pending_assistant["tool_calls"] = pending_tool_calls
                pending_tool_calls.append(
                    {
                        "id": item.call_id,
                        "type": "function",
                        "function": {
                            "name": item.name,
                            "arguments": item.arguments or "{}",
                        },
                    }
                )
                tool_names_by_call_id[item.call_id] = item.name
                continue
            if isinstance(item, FunctionCallOutput):
                flush_assistant()
                name = tool_names_by_call_id.get(item.call_id)
                if name is None:
                    raise ValueError(
                        "LiteRT-LM cannot convert a function output without the "
                        f"matching function call: {item.call_id}"
                    )
                messages.append(
                    {
                        "role": "tool",
                        "content": [
                            {
                                "type": "tool_response",
                                "name": name,
                                "response": RockyMessages.to_json_value(item.output),
                            }
                        ],
                    }
                )
                continue

            if isinstance(item, EasyInputMessage | Message | ResponseOutputMessage):
                message = {
                    "role": item.role,
                    "content": cls.content_parts_from_agents_content(item.content),
                }
                if item.role == "assistant":
                    flush_assistant()
                    pending_assistant = message
                else:
                    flush_assistant()
                    messages.append(message)
                continue

            raise ValueError(
                f"Unsupported Agents SDK input item: {type(item).__name__}"
            )

        flush_assistant()
        return messages

    @classmethod
    def content_parts_from_agents_content(
        cls,
        content: (
            str
            | Iterable[
                ResponseInputContent
                | ResponseInputAudio
                | ResponseOutputMessageContent
                | ResponseFunctionCallOutputContent
            ]
        ),
    ) -> list[dict[str, object]]:
        if isinstance(content, str):
            return [{"type": "text", "text": content}] if content else []
        parts: list[dict[str, object]] = []
        for part in content:
            converted = cls.content_part_from_agents_content_part(part)
            if converted is not None:
                parts.append(converted)
        return parts

    @classmethod
    def content_part_from_agents_content_part(
        cls,
        part: (
            ResponseInputContent
            | ResponseInputAudio
            | ResponseOutputMessageContent
            | ResponseFunctionCallOutputContent
        ),
    ) -> dict[str, object] | None:
        if isinstance(part, ResponseInputText | ResponseInputTextContent):
            return {"type": "text", "text": part.text}
        if isinstance(part, ResponseOutputText):
            return {"type": "text", "text": part.text}
        if isinstance(part, ResponseOutputRefusal):
            return {"type": "text", "text": part.refusal}
        if isinstance(part, ResponseInputImage | ResponseInputImageContent):
            image_url = part.image_url
            if image_url:
                return {
                    "type": "image",
                    "blob": cls.image_blob_from_agents_image_url(image_url),
                }
            logger.warning(
                "LiteRT-LM cannot convert image content without image_url; skipping %s",
                type(part).__name__,
            )
            return None
        if isinstance(part, ResponseInputAudio):
            return {
                "type": "audio",
                "blob": part.input_audio.data,
                "format": part.input_audio.format,
            }
        if isinstance(part, ResponseInputFile | ResponseInputFileContent):
            filename = part.filename
            detail = f" ({filename})" if isinstance(filename, str) and filename else ""
            logger.warning(
                "LiteRT-LM does not support file content parts; skipping %s%s",
                type(part).__name__,
                detail,
            )
            return None
        logger.warning(
            "Unsupported Agents SDK content part for LiteRT-LM; skipping %s",
            type(part).__name__,
        )
        return None

    @staticmethod
    def image_blob_from_agents_image_url(url: str) -> str:
        return url.split(",", 1)[1] if url.startswith("data:") and "," in url else url

    @classmethod
    def has_images(cls, message: dict[str, object]) -> bool:
        content = message.get("content")
        return isinstance(content, list) and any(
            isinstance(part, dict) and part.get("type") == "image" for part in content
        )

    @classmethod
    def messages_key(cls, messages: list[dict[str, object]]) -> str:
        digest = hashlib.sha256()
        encoder = json.JSONEncoder(
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        for chunk in encoder.iterencode(messages):
            digest.update(chunk.encode("utf-8"))
        return f"sha256:{digest.hexdigest()}"

    @classmethod
    def tools_key(cls, tools: list[Tool]) -> str:
        values: list[dict[str, object]] = []
        for tool in tools:
            if not isinstance(tool, FunctionTool):
                continue
            parameters = tool.params_json_schema
            if not isinstance(parameters, dict):
                parameters = {"type": "object", "properties": {}}
            values.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": parameters,
                }
            )
        digest = hashlib.sha256()
        encoder = json.JSONEncoder(
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        for chunk in encoder.iterencode(values):
            digest.update(chunk.encode("utf-8"))
        return f"sha256:{digest.hexdigest()}"

    @classmethod
    def replace_history_multimodal(
        cls,
        messages: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return [cls.replace_message_multimodal(message) for message in messages]

    @classmethod
    def replace_message_multimodal(
        cls,
        message: dict[str, object],
    ) -> dict[str, object]:
        content = message.get("content")
        if not isinstance(content, list):
            return message
        changed = False
        parts: list[object] = []
        for part in content:
            if cls.is_multimodal_part(part):
                changed = True
                parts.append({"type": "text", "text": _HISTORY_MULTIMODAL_PLACEHOLDER})
            else:
                parts.append(part)
        if not changed:
            return message
        updated = dict(message)
        updated["content"] = parts
        return updated

    @staticmethod
    def is_multimodal_part(part: object) -> bool:
        return isinstance(part, dict) and part.get("type") in ("image", "audio", "file")


class LitertLmActiveConversation:
    _conversation: Any | None = None
    _model_path: str | None = None
    _vision = False
    _tools_key = ""
    _history_key = ""
    _messages: list[dict[str, object]] = []

    @classmethod
    def get(
        cls,
        *,
        model_path: str,
        vision: bool,
        tools_key: str,
        history_key: str,
        history: list[dict[str, object]],
        engine: Any,
        kwargs: dict[str, Any],
    ) -> Any:
        if cls._can_reuse(
            model_path=model_path,
            vision=vision,
            tools_key=tools_key,
            history_key=history_key,
        ):
            logger.warning(
                "Reusing LiteRT-LM conversation (model_path=%s, vision=%s)",
                model_path,
                vision,
            )
            return cls._conversation
        logger.warning(
            "Creating LiteRT-LM conversation (model_path=%s, vision=%s)",
            model_path,
            vision,
        )
        cls.close()
        conversation = engine.create_conversation(**kwargs)
        conversation.__enter__()
        cls._conversation = conversation
        cls._model_path = model_path
        cls._vision = vision
        cls._tools_key = tools_key
        cls._history_key = history_key
        cls._messages = list(history)
        return conversation

    @classmethod
    def save(
        cls,
        *,
        current: dict[str, object],
        output_messages: list[dict[str, object]],
    ) -> None:
        if cls._conversation is None:
            return
        cls._messages = LitertLmMessages.replace_history_multimodal(
            cls._messages + [current] + output_messages
        )
        cls._history_key = LitertLmMessages.messages_key(cls._messages)

    @classmethod
    def close(cls) -> None:
        conversation = cls._conversation
        cls._conversation = None
        cls._model_path = None
        cls._vision = False
        cls._tools_key = ""
        cls._history_key = ""
        cls._messages = []
        if conversation is None:
            return
        try:
            conversation.__exit__(None, None, None)
        except Exception:
            logger.exception("Failed to close cached LiteRT-LM conversation")

    @classmethod
    def _can_reuse(
        cls,
        *,
        model_path: str,
        vision: bool,
        tools_key: str,
        history_key: str,
    ) -> bool:
        if cls._conversation is None:
            return False
        if cls._model_path != model_path or cls._tools_key != tools_key:
            return False
        return cls._vision == vision and cls._history_key == history_key


class LitertLmModel(Model):
    def __init__(self, model_path: str):
        if not model_path:
            raise ValueError("model_path is required for LitertLmModel")
        self._model_path = model_path
        LitertLmEngineCache.get(model_path=model_path, vision=False)

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
        tools: list[Tool],
        output_schema: Any,
        handoffs: list[Any],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> ModelResponse:
        output = self._send_message(
            system_instructions=system_instructions,
            input=input,
            tools=tools,
            label="get_response",
        )
        return self._build_response(output)

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: Any,
        tools: list[Tool],
        output_schema: Any,
        handoffs: list[Any],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> AsyncIterator[TResponseStreamEvent]:
        output = self._send_message(
            system_instructions=system_instructions,
            input=input,
            tools=tools,
            label="stream_response",
        )
        emitter = ResponseStreamEmitter(
            event_id=new_litertlm_id("litertlm-"),
            model_label=self.model_label,
        )
        for event in emitter.emit(output):
            yield event
        await asyncio.sleep(0)

    def _send_message(
        self,
        *,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        tools: list[Tool],
        label: str,
    ) -> list[ResponseInputItem]:
        history, current, history_has_images = (
            self._litertlm_history_and_current_message(system_instructions, input)
        )
        vision = LitertLmMessages.has_images(current) or (
            LITERTLM_KEEP_VISION_IF_HISTORY_HAS_IMAGES and history_has_images
        )
        tools_key = LitertLmMessages.tools_key(tools)
        history_key = LitertLmMessages.messages_key(history)
        engine = LitertLmEngineCache.get(model_path=self._model_path, vision=vision)
        kwargs = self._conversation_kwargs(history=history, tools=tools)
        try:
            conversation = LitertLmActiveConversation.get(
                model_path=self._model_path,
                vision=vision,
                tools_key=tools_key,
                history_key=history_key,
                history=history,
                engine=engine,
                kwargs=kwargs,
            )
            chunk = conversation.send_message(current)
            output = self._build_output(chunk)
            output_messages = LitertLmMessages.from_agents_input_items(output)
            LitertLmActiveConversation.save(
                current=current,
                output_messages=output_messages,
            )
            return output
        except BaseException:
            LitertLmActiveConversation.close()
            logger.error(
                "%s failed (vision=%s):\n%s",
                label,
                vision,
                traceback.format_exc(),
            )
            raise

    def _litertlm_history_and_current_message(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
    ) -> tuple[list[dict[str, object]], dict[str, object], bool]:
        input_items = self._agents_runtime_input_items(system_instructions, input)
        if not input_items:
            raise ValueError("LiteRT-LM requires at least one Agents SDK input item")
        current_item = input_items[-1]
        if not (
            isinstance(current_item, FunctionCallOutput)
            or (
                isinstance(
                    current_item,
                    EasyInputMessage | Message | ResponseOutputMessage,
                )
                and current_item.role in ("developer", "user")
            )
        ):
            raise ValueError(
                "LiteRT-LM current input must end with a user/developer message "
                "or a function call output"
            )
        messages = LitertLmMessages.from_agents_input_items(input_items)
        if not messages:
            raise ValueError("LiteRT-LM requires at least one converted message")
        history_has_images = any(
            LitertLmMessages.has_images(message) for message in messages[:-1]
        )
        history = LitertLmMessages.replace_history_multimodal(messages[:-1])
        return (
            history,
            messages[-1],
            history_has_images,
        )

    def _agents_runtime_input_items(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
    ) -> list[ResponseInputItem]:
        input_items = ItemHelpers.input_to_new_input_list(input)
        if system_instructions:
            input_items.insert(0, {"role": "system", "content": system_instructions})
        return [
            _RESPONSE_INPUT_ITEM_ADAPTER.validate_python(item) for item in input_items
        ]

    def _build_response(self, output: list[ResponseInputItem]) -> ModelResponse:
        return ModelResponse(output=output, usage=Usage(requests=1), response_id=None)

    def _build_output(self, chunk: Any) -> list[ResponseInputItem]:
        output: list[ResponseInputItem] = []
        text = self._extract_text(chunk)
        if text:
            output.append(self._build_message(text=text))
        output.extend(self._extract_tool_calls(chunk))
        return output

    def _build_message(self, *, text: str) -> ResponseOutputMessage:
        message = ResponseOutputMessage(
            id=new_litertlm_id("litertlm-"),
            content=[ResponseOutputText(text=text, type="output_text", annotations=[])],
            role="assistant",
            type="message",
            status="completed",
        )
        return message

    def _conversation_kwargs(
        self,
        *,
        history: list[dict[str, object]],
        tools: list[Tool],
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if history:
            kwargs["messages"] = history
        litertlm_tools = LitertLmMessages.from_agents_tools(tools)
        if litertlm_tools:
            kwargs["tools"] = litertlm_tools
            kwargs["automatic_tool_calling"] = False
            kwargs["enable_constrained_decoding"] = True
        return kwargs

    @staticmethod
    def _extract_text(chunk: Any) -> str:
        parts: list[str] = []
        if not isinstance(chunk, dict):
            return ""
        content = chunk.get("content")
        if isinstance(content, str):
            return content
        for item in content or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text = item.get("text") or ""
                if text:
                    parts.append(text)
        return "".join(parts)

    def _extract_tool_calls(self, chunk: Any) -> list[ResponseFunctionToolCall]:
        if not isinstance(chunk, dict):
            return []
        raw_calls = chunk.get("tool_calls") or []
        if not raw_calls:
            raw_calls = [
                item
                for item in chunk.get("content", []) or []
                if isinstance(item, dict)
                and item.get("type") in ("tool_call", "function_call")
            ]
        calls: list[ResponseFunctionToolCall] = []
        for raw_call in raw_calls:
            if isinstance(raw_call, dict):
                call = self._build_tool_call(raw_call)
                if call is not None:
                    calls.append(call)
        return calls

    def _build_tool_call(
        self, raw_call: dict[str, Any]
    ) -> ResponseFunctionToolCall | None:
        function = raw_call.get("function")
        function = function if isinstance(function, dict) else {}
        name = function.get("name") or raw_call.get("name")
        if not isinstance(name, str) or not name:
            logger.warning(
                "Skipping LiteRT-LM tool call without a function name: %s", raw_call
            )
            return None
        arguments = self._stringify_arguments(
            function.get("arguments")
            if "arguments" in function
            else raw_call.get("arguments", raw_call.get("parameters"))
        )
        call_id = (
            raw_call.get("call_id")
            or raw_call.get("id")
            or new_litertlm_id("litertlm-call-")
        )
        return ResponseFunctionToolCall(
            id=new_litertlm_id("litertlm-"),
            call_id=str(call_id),
            arguments=arguments,
            name=name,
            type="function_call",
            status="completed",
        )

    @classmethod
    def _stringify_arguments(cls, arguments: Any) -> str:
        if arguments is None or arguments == "":
            return "{}"
        if isinstance(arguments, str):
            return arguments
        return json.dumps(arguments, ensure_ascii=False, default=str)
