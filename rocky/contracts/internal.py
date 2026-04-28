from __future__ import annotations

import hashlib

from flut.dart import Color
from flut.flutter.material import DynamicSchemeVariant
from pydantic import BaseModel, Field

from rocky.contracts.shell import RockyRuntimeShellEnvironment


class RockyThemeOption:
    def __init__(
        self,
        *,
        id: str,
        label: str,
        seed: Color,
        variant: DynamicSchemeVariant,
    ):
        self.id = id
        self.label = label
        self.seed = seed
        self.variant = variant


class RockyRuntimeState(BaseModel):
    shell_environments: list[RockyRuntimeShellEnvironment] = Field(default_factory=list)

    def fingerprint(self) -> str:
        payload = self.model_dump_json()
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
