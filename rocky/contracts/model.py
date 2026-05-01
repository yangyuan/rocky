from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

RockyModelCapabilityValue = bool | int | float | str


class RockyModelProviderName(str, Enum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    LITERTLM = "litertlm"


class RockyModelApi(str, Enum):
    CHAT_COMPLETIONS = "chat_completions"
    RESPONSES = "responses"


class RockyModelCapabilityName(str, Enum):
    FUNCTION = "function"


class RockyModelCapabilityType(str, Enum):
    BOOL = "bool"
    INTEGER = "int"
    FLOAT = "float"
    STRING = "str"


class RockyModelCapabilityDefinition(BaseModel):
    name: RockyModelCapabilityName
    label: str
    type: RockyModelCapabilityType
    default: RockyModelCapabilityValue


class RockyModelCapability(BaseModel):
    name: RockyModelCapabilityName
    value: RockyModelCapabilityValue


class RockyModelTemplate(BaseModel):
    name: str
    label: str
    caption: Optional[str] = None
    capabilities: Optional[list[RockyModelCapability]] = None
    recommended: bool = False
    local_filename: Optional[str] = None
    download_url: Optional[str] = None
    size_bytes: Optional[int] = None


class RockyModelProviderCatalog(BaseModel):
    capabilities: list[RockyModelCapability] = Field(default_factory=list)
    models: list[RockyModelTemplate] = Field(default_factory=list)


class RockyModelManifest(BaseModel):
    capabilities: list[RockyModelCapabilityDefinition]
    providers: dict[RockyModelProviderName, RockyModelProviderCatalog]


class RockyModelProfile(BaseModel):
    id: str
    display_name: str = "Untitled model"
    provider: RockyModelProviderName = RockyModelProviderName.OPENAI
    api: RockyModelApi = RockyModelApi.CHAT_COMPLETIONS
    name: str = ""
    capabilities: list[RockyModelCapability] = Field(default_factory=list)
    key: str = ""
    endpoint: str = ""
    deployment: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
