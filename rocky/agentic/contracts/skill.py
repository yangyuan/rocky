from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class SkillSource(StrEnum):
    SYSTEM = "system"
    USER = "user"


class Skill(BaseModel):
    id: str
    name: str
    description: str
    source: SkillSource
    path: str
