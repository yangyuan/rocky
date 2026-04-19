from __future__ import annotations

import base64
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Iterable, Sequence, TypedDict

from agents.items import TResponseInputItem
from agents.models.chatcmpl_converter import Converter

logger = logging.getLogger(__name__)


class LocalMessagePart(TypedDict, total=False):
    type: str
    text: str
    path: str


class LocalMessage(TypedDict):
    role: str
    content: list[LocalMessagePart]


class LocalImageAttachment:
    def __init__(self, *, mime_type: str, raw: bytes):
        extension = mime_type.split("/")[-1] or "bin"
        handle = tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False)
        try:
            handle.write(raw)
        finally:
            handle.close()
        self._path = handle.name

    def as_message_part(self) -> LocalMessagePart:
        return {"type": "image", "path": self._path}

    def discard(self) -> None:
        try:
            os.unlink(self._path)
        except OSError:
            pass


@dataclass
class LocalMessageBundle:
    messages: list[LocalMessage]
    attachments: list[LocalImageAttachment] = field(default_factory=list)

    def __enter__(self) -> "LocalMessageBundle":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        del exc_type, exc_val, exc_tb
        self.discard()

    @property
    def has_images(self) -> bool:
        return any(
            part.get("type") == "image"
            for message in self.messages
            for part in message.get("content") or []
        )

    def discard(self) -> None:
        for attachment in self.attachments:
            attachment.discard()
        self.attachments = []

    def replace_history_images(self, placeholder_text: str) -> None:
        if len(self.messages) <= 1:
            return
        history, current = self.messages[:-1], self.messages[-1]
        rewritten: list[LocalMessage] = []
        for message in history:
            new_parts: list[LocalMessagePart] = []
            for part in message.get("content") or []:
                if part.get("type") == "image":
                    new_parts.append({"type": "text", "text": placeholder_text})
                else:
                    new_parts.append(part)
            rewritten.append({"role": message["role"], "content": new_parts})
        rewritten.append(current)
        self.messages = rewritten


class LocalMessageBuilder:
    @classmethod
    def build(
        cls,
        *,
        system_instructions: str | None,
        items: str | Iterable[TResponseInputItem],
    ) -> LocalMessageBundle:
        bundle = LocalMessageBundle(messages=[])
        if system_instructions:
            bundle.messages.append(
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_instructions}],
                }
            )
        for raw in Converter.items_to_messages(items):
            message = cls._convert_message(raw, bundle.attachments)
            if message is not None:
                bundle.messages.append(message)
        return bundle

    @classmethod
    def _convert_message(
        cls,
        raw: dict,
        attachments: list[LocalImageAttachment],
    ) -> LocalMessage | None:
        role = raw.get("role") or "user"
        content = raw.get("content")
        parts: list[LocalMessagePart] = []
        if isinstance(content, str):
            if content:
                parts.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for raw_part in content:
                if not isinstance(raw_part, dict):
                    continue
                converted = cls._convert_part(raw_part, attachments)
                if converted is not None:
                    parts.append(converted)
        if not parts:
            return None
        return {"role": role, "content": parts}

    @classmethod
    def _convert_part(
        cls,
        raw: dict,
        attachments: list[LocalImageAttachment],
    ) -> LocalMessagePart | None:
        part_type = raw.get("type")
        if part_type in ("text", "input_text", "output_text"):
            text = raw.get("text") or ""
            if text:
                return {"type": "text", "text": text}
            return None
        if part_type == "image_url":
            attachment = cls._decode_image_url(raw)
            if attachment is None:
                return None
            attachments.append(attachment)
            return attachment.as_message_part()
        return None

    @classmethod
    def _decode_image_url(cls, raw: dict) -> LocalImageAttachment | None:
        url = raw.get("image_url") or {}
        if isinstance(url, dict):
            url = url.get("url", "")
        if not isinstance(url, str):
            return None
        if not url.startswith("data:") or "," not in url:
            return None
        header, b64_data = url.split(",", 1)
        mime_type = header[len("data:") :].split(";")[0] or "application/octet-stream"
        try:
            raw_bytes = base64.b64decode(b64_data)
        except (ValueError, base64.binascii.Error) as exc:
            logger.warning("Skipping malformed image_url data: %s", exc)
            return None
        return LocalImageAttachment(mime_type=mime_type, raw=raw_bytes)


class LocalMessageLogSummary:
    @classmethod
    def format(cls, messages: Sequence[LocalMessage]) -> str:
        return " | ".join(cls._format_message(m) for m in messages)

    @classmethod
    def _format_message(cls, message: LocalMessage) -> str:
        role = message.get("role", "?")
        rendered = [cls._format_part(p) for p in message.get("content") or []]
        return f"{role}:[{', '.join(rendered)}]"

    @classmethod
    def _format_part(cls, part: LocalMessagePart) -> str:
        part_type = part.get("type", "?")
        if part_type == "text":
            text = (part.get("text") or "").replace("\n", " ")
            preview = text if len(text) <= 80 else text[:80] + "\u2026"
            return f"text({len(part.get('text') or '')}ch:{preview!r})"
        if part_type == "image":
            return f"image({part.get('path', '?')})"
        return part_type


def new_response_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"
