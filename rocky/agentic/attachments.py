from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from rocky.contracts.chat import RockyAttachment

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
    SUPPORTED_EXTENSIONS: dict[str, str] = {**IMAGE_MIME_TYPES, **TEXT_MIME_TYPES}
    MAX_BYTES: int = 16 * 1024 * 1024

    @classmethod
    def is_image(cls, attachment: RockyAttachment) -> bool:
        return attachment.mime_type.startswith("image/")

    @classmethod
    def is_text(cls, attachment: RockyAttachment) -> bool:
        return attachment.mime_type.startswith("text/")

    @classmethod
    def data_url(cls, attachment: RockyAttachment) -> str:
        return f"data:{attachment.mime_type};base64,{attachment.data}"

    @classmethod
    def decoded_bytes(cls, attachment: RockyAttachment) -> bytes:
        return base64.b64decode(attachment.data)

    @classmethod
    def decoded_text(cls, attachment: RockyAttachment) -> str:
        return cls.decoded_bytes(attachment).decode("utf-8", errors="replace")

    @classmethod
    def load(cls, path: Path) -> Optional[RockyAttachment]:
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
        return RockyAttachment(
            filename=path.name,
            mime_type=mime_type,
            data=base64.b64encode(raw).decode("ascii"),
        )
