from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from rocky.contracts.chat import (
    RockyChatContent,
    RockyChatFileContentPart,
    RockyChatImageContentPart,
    RockyChatTextContentPart,
)

logger = logging.getLogger(__name__)


class RockyAttachments:
    IMAGE_MIME_TYPES: dict[str, str] = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    TEXT_MIME_TYPES: dict[str, str] = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".py": "text/x-python",
        ".json": "text/json",
        ".csv": "text/csv",
    }
    FILE_MIME_TYPES: dict[str, str] = {
        ".pdf": "application/pdf",
    }
    SUPPORTED_EXTENSIONS: dict[str, str] = {
        **IMAGE_MIME_TYPES,
        **TEXT_MIME_TYPES,
        **FILE_MIME_TYPES,
    }
    MAX_BYTES: int = 16 * 1024 * 1024

    @classmethod
    def is_image(cls, attachment: RockyChatFileContentPart) -> bool:
        mime_type = cls.mime_type(attachment)
        return bool(mime_type and mime_type.startswith("image/"))

    @classmethod
    def is_text(cls, attachment: RockyChatFileContentPart) -> bool:
        mime_type = cls.mime_type(attachment)
        return bool(mime_type and mime_type.startswith("text/"))

    @classmethod
    def mime_type(cls, attachment: RockyChatFileContentPart) -> Optional[str]:
        file_data = attachment.file_data or ""
        if file_data.startswith("data:") and "," in file_data:
            header = file_data.split(",", 1)[0]
            return header[len("data:") :].split(";")[0] or None
        if attachment.filename:
            return cls.SUPPORTED_EXTENSIONS.get(
                Path(attachment.filename).suffix.lower()
            )
        return None

    @classmethod
    def data_url(cls, attachment: RockyChatFileContentPart) -> str:
        file_data = attachment.file_data or ""
        if file_data.startswith("data:"):
            return file_data
        mime_type = cls.mime_type(attachment)
        return f"data:{mime_type};base64,{file_data}" if mime_type else file_data

    @classmethod
    def decoded_bytes(cls, attachment: RockyChatFileContentPart) -> bytes:
        file_data = attachment.file_data or ""
        if file_data.startswith("data:") and "," in file_data:
            file_data = file_data.split(",", 1)[1]
        return base64.b64decode(file_data)

    @classmethod
    def decoded_text(cls, attachment: RockyChatFileContentPart) -> str:
        return cls.decoded_bytes(attachment).decode("utf-8", errors="replace")

    @classmethod
    def message_content(
        cls,
        text: str,
        attachments: list[RockyChatFileContentPart],
    ) -> RockyChatContent:
        if not attachments:
            return text
        parts: list[
            RockyChatTextContentPart
            | RockyChatImageContentPart
            | RockyChatFileContentPart
        ] = []
        if text:
            parts.append(RockyChatTextContentPart(text=text))
        for attachment in attachments:
            parts.append(
                RockyChatTextContentPart(text=f"[Attached file: {attachment.filename}]")
            )
            if cls.is_image(attachment):
                parts.append(
                    RockyChatImageContentPart(image_url=cls.data_url(attachment))
                )
            elif cls.is_text(attachment):
                body = cls.decoded_text(attachment) if cls.is_text(attachment) else ""
                parts.append(RockyChatTextContentPart(text=body))
            else:
                parts.append(attachment)
        return parts

    @classmethod
    def load(cls, path: Path) -> Optional[RockyChatFileContentPart]:
        extension = path.suffix.lower()
        mime_type = cls.SUPPORTED_EXTENSIONS.get(extension)
        if mime_type is None:
            logger.warning("Skipping unsupported attachment %s", path.name)
            return None
        try:
            raw = path.read_bytes()
        except OSError as exc:
            logger.warning("Failed to read attachment %s: %s", path, exc)
            return None
        if len(raw) > cls.MAX_BYTES:
            logger.warning(
                "Skipping attachment %s: %d bytes exceeds %d-byte cap",
                path.name,
                len(raw),
                cls.MAX_BYTES,
            )
            return None
        return RockyChatFileContentPart(
            file_data=f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}",
            filename=path.name,
        )
