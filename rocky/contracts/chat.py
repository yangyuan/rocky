from __future__ import annotations

import time
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

DEFAULT_CHAT_TITLE = "New chat"


class RockyAttachment(BaseModel):
    filename: str
    mime_type: str
    data: str


class RockyToolCall(BaseModel):
    id: str = ""
    name: str = "tool"
    arguments: object = None
    output: object = None
    completed: bool = False


class RockyChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "developer", "tool"]
    content: str = ""
    streaming: bool = False
    attachments: list[RockyAttachment] = Field(default_factory=list)
    tool_calls: list[RockyToolCall] = Field(default_factory=list)


class RockyChatMetadata(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str = DEFAULT_CHAT_TITLE
    custom_title: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    model_id: Optional[str] = None
    shell_ids: Optional[list[str]] = None
    skill_ids: Optional[list[str]] = None
    workspace_folder: Optional[str] = None


class RockyChatData(BaseModel):
    messages: list[RockyChatMessage] = Field(default_factory=list)
