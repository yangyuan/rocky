from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from rocky.contracts.model import RockyModelProfile
from rocky.contracts.shell import RockyShellProfile


class RockyAgentConfig(BaseModel):
    model_profile: RockyModelProfile
    shell_profiles: list[RockyShellProfile] = Field(default_factory=list)


class RockyAgentStatus(str, Enum):
    UNCONFIGURED = "unconfigured"
    INITIALIZING = "initializing"
    READY = "ready"
    SENDING = "sending"
    THINKING = "thinking"
    RESPONDING = "responding"
    EXECUTING = "executing"


class RockyAgentStreamEventKind(str, Enum):
    GENERATION_STARTED = "generation_started"
    TEXT_DELTA = "text_delta"
    MESSAGE_BOUNDARY = "message_boundary"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    REASONING = "reasoning"


class RockyAgentStreamEvent:
    type: RockyAgentStreamEventKind

    def __init__(
        self,
        event_type: RockyAgentStreamEventKind,
        *,
        delta: str = "",
    ) -> None:
        self.type = event_type
        self.delta = delta
