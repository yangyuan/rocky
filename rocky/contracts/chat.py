from __future__ import annotations

import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_CHAT_TITLE = "New chat"


class RockyAttachment(BaseModel):
    filename: str
    mime_type: str
    data: str


class RockyChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = ""
    streaming: bool = False
    attachments: list[RockyAttachment] = Field(default_factory=list)


class RockyChatMetadata(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str = DEFAULT_CHAT_TITLE
    custom_title: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class RockyChatData(BaseModel):
    metadata: RockyChatMetadata
    messages: list[RockyChatMessage] = Field(default_factory=list)
