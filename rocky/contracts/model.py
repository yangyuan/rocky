from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

RockyModelProvider = Literal["openai", "azure_openai", "litertlm"]


class RockyModelTemplate(BaseModel):
    name: str
    label: str
    caption: Optional[str] = None
    recommended: bool = False
    local_filename: Optional[str] = None
    download_url: Optional[str] = None
    size_bytes: Optional[int] = None


class RockyModelProfile(BaseModel):
    id: str
    display_name: str = "Untitled model"
    provider: RockyModelProvider = "openai"
    name: str = ""
    key: str = ""
    endpoint: str = ""
    deployment: str = ""
