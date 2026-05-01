from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class RockyMcpServerType(StrEnum):
    STDIO = "stdio"
    HTTP = "http"


class RockyStdioMcpServerProperties(BaseModel):
    command: str = ""


class RockyHttpMcpServerProperties(BaseModel):
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


RockyMcpServerProperties = RockyStdioMcpServerProperties | RockyHttpMcpServerProperties


class RockyMcpServerProfile(BaseModel):
    id: str
    display_name: str = ""
    server_type: RockyMcpServerType = RockyMcpServerType.STDIO
    timeout: Optional[float] = None
    properties: RockyMcpServerProperties = Field(
        default_factory=RockyStdioMcpServerProperties
    )


class RockyRuntimeMcpServer(BaseModel):
    id: str
    name: str
    type: RockyMcpServerType
