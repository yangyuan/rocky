from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

ROCKY_LOCAL_SHELL_PROFILE_ID = "local"

RockyShellType = Literal[
    "local",
    "docker",
    "docker_in_wsl",
    "docker_over_ssh",
    "ssh",
    "wsl",
]

RockyRuntimeShellKind = Literal["local", "remote"]
RockyRuntimeShellOS = Literal["windows", "macos", "linux"]


class RockyShellProfile(BaseModel):
    id: str
    display_name: str = ""
    shell_type: RockyShellType = "docker"
    name: str = ""
    host: str = ""
    output_max_head_tail: Optional[int] = 20000


class RockyRuntimeShellEnvironment(BaseModel):
    id: str
    name: str
    kind: RockyRuntimeShellKind = "remote"
    os: Optional[RockyRuntimeShellOS] = None
