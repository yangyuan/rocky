from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

RockyShellType = Literal[
    "docker",
    "docker_in_wsl",
    "docker_over_ssh",
    "ssh",
    "wsl",
]


class RockyShellProfile(BaseModel):
    id: str
    display_name: str = "Untitled environment"
    shell_type: RockyShellType = "docker"
    name: str = ""
    host: str = ""
    output_max_head_tail: Optional[int] = 20000


class RockyShellReference(BaseModel):
    id: str
    name: str
