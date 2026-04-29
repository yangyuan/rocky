from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from rocky.contracts.model import RockyModelProfile
from rocky.contracts.shell import RockyShellProfile


class RockyThemeSettings(BaseModel):
    color: str = "default"
    brightness: str = "light"
    tint: bool = True


class RockyChatsSettings(BaseModel):
    max_chats: Optional[int] = None


class RockySettingsData(BaseModel):
    theme: RockyThemeSettings = Field(default_factory=RockyThemeSettings)
    chats: RockyChatsSettings = Field(default_factory=RockyChatsSettings)
    models: list[RockyModelProfile] = Field(default_factory=list)
    default_model_id: Optional[str] = None
    shells: list[RockyShellProfile] = Field(default_factory=list)
    default_shell_ids: list[str] = Field(default_factory=list)
    default_skill_ids: list[str] = Field(default_factory=list)
