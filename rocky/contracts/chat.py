from __future__ import annotations

from enum import StrEnum
import time
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

DEFAULT_CHAT_TITLE = "New chat"


class RockyChatContentPartType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"


class RockyChatTextContentPart(BaseModel):
    type: Literal[RockyChatContentPartType.TEXT] = RockyChatContentPartType.TEXT
    text: str


class RockyChatImageDetail(StrEnum):
    AUTO = "auto"
    LOW = "low"
    HIGH = "high"


class RockyChatImageContentPart(BaseModel):
    type: Literal[RockyChatContentPartType.IMAGE] = RockyChatContentPartType.IMAGE
    image_url: str
    detail: RockyChatImageDetail = RockyChatImageDetail.AUTO


class RockyChatFileContentPart(BaseModel):
    type: Literal[RockyChatContentPartType.FILE] = RockyChatContentPartType.FILE
    file_data: Optional[str] = None
    filename: Optional[str] = None


RockyChatContentPart = (
    RockyChatTextContentPart | RockyChatImageContentPart | RockyChatFileContentPart
)
RockyChatContent = list[RockyChatContentPart] | str
RockyJsonScalar = None | bool | int | float | str
type RockyJsonValue = RockyJsonScalar | list[RockyJsonValue] | dict[str, RockyJsonValue]


class RockyToolCall(BaseModel):
    id: str = ""
    name: str = "tool"
    arguments: dict | str = Field(default_factory=dict)
    output: RockyJsonValue = None
    completed: bool = False


class RockyChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "developer", "tool"]
    content: Optional[RockyChatContent] = None
    tool_calls: Optional[list[RockyToolCall]] = None
    tool_call_id: Optional[str] = None


class RockyChatMetadata(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str = DEFAULT_CHAT_TITLE
    custom_title: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    model_id: Optional[str] = None
    shell_ids: Optional[list[str]] = None
    skill_ids: Optional[list[str]] = None
    mcp_server_ids: Optional[list[str]] = None
    workspace_folder: Optional[str] = None


class RockyChatData(BaseModel):
    messages: list[RockyChatMessage] = Field(default_factory=list)


class RockyChatTemplateMetadata(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    model_id: Optional[str] = None
    shell_ids: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)


class RockyChatTemplateData(BaseModel):
    messages: list[RockyChatMessage] = Field(default_factory=list)
    input_text: str = ""
    input_attachments: list[RockyChatFileContentPart] = Field(default_factory=list)


class RockyChatTemplate(BaseModel):
    metadata: RockyChatTemplateMetadata
    data: RockyChatTemplateData = Field(default_factory=RockyChatTemplateData)

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def title(self) -> str:
        return self.metadata.title
