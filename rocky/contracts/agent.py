from __future__ import annotations

from enum import StrEnum
from typing import Optional, TypeAlias

from pydantic import BaseModel, Field

from rocky.agentic.contracts.skill import Skill
from rocky.contracts.chat import RockyChatMessage
from rocky.contracts.mcp import RockyMcpServerProfile
from rocky.contracts.model import RockyModelProfile
from rocky.contracts.shell import RockyShellProfile


class RockyAgentConfig(BaseModel):
    model_profile: RockyModelProfile
    shell_profiles: list[RockyShellProfile] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    mcp_server_profiles: list[RockyMcpServerProfile] = Field(default_factory=list)
    workspace_folder: str


class RockyAgentStatus(StrEnum):
    UNCONFIGURED = "unconfigured"
    INITIALIZING = "initializing"
    READY = "ready"
    SENDING = "sending"
    THINKING = "thinking"
    RESPONDING = "responding"
    EXECUTING = "executing"


class RockyChatChunkEvent(BaseModel):
    state: Optional[RockyAgentStatus] = None
    delta: Optional[str] = None


RockyStreamEvent: TypeAlias = RockyChatChunkEvent | RockyChatMessage
