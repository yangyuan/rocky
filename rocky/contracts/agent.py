from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from rocky.contracts.model import RockyModelProfile


class RockyAgentConfig(BaseModel):
    model_profile: RockyModelProfile


class RockyAgentStatus(str, Enum):
    UNCONFIGURED = "unconfigured"
    INITIALIZING = "initializing"
    READY = "ready"
    SENDING = "sending"
    RESPONDING = "responding"
