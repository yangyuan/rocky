from __future__ import annotations

from pathlib import Path
from typing import Optional

from rocky.contracts.model import (
    RockyModelCapability,
    RockyModelCapabilityDefinition,
    RockyModelManifest,
    RockyModelProviderName,
    RockyModelProviderCatalog,
    RockyModelTemplate,
)

_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "configs" / "models.json"


class RockyModelTemplates:
    PROVIDERS: tuple[RockyModelProviderName, ...] = (
        RockyModelProviderName.OPENAI,
        RockyModelProviderName.AZURE_OPENAI,
        RockyModelProviderName.LITERTLM,
    )
    LABELS: dict[RockyModelProviderName, str] = {
        RockyModelProviderName.OPENAI: "OpenAI",
        RockyModelProviderName.AZURE_OPENAI: "Azure OpenAI",
        RockyModelProviderName.LITERTLM: "LiteRT-LM",
    }

    _manifest: Optional[RockyModelManifest] = None

    def __init__(self):
        raise TypeError("RockyModelTemplates is a static class.")

    @classmethod
    def _load(cls) -> RockyModelManifest:
        if cls._manifest is None:
            cls._manifest = RockyModelManifest.model_validate_json(
                _MANIFEST_PATH.read_text(encoding="utf-8")
            )
        return cls._manifest

    @classmethod
    def capability_definitions(cls) -> list[RockyModelCapabilityDefinition]:
        return list(cls._load().capabilities)

    @classmethod
    def providers(cls) -> tuple[RockyModelProviderName, ...]:
        return cls.PROVIDERS

    @classmethod
    def label(cls, provider: RockyModelProviderName) -> str:
        return cls.LABELS.get(provider, provider.value)

    @classmethod
    def all(cls, provider: RockyModelProviderName) -> list[RockyModelTemplate]:
        return list(
            cls._load().providers.get(provider, RockyModelProviderCatalog()).models
        )

    @classmethod
    def find(
        cls, provider: RockyModelProviderName, name: str
    ) -> Optional[RockyModelTemplate]:
        for template in (
            cls._load()
            .providers.get(
                provider,
                RockyModelProviderCatalog(),
            )
            .models
        ):
            if template.name == name:
                return template
        return None

    @classmethod
    def capability_overrides(
        cls, provider: RockyModelProviderName, name: str = ""
    ) -> list[RockyModelCapability]:
        catalog = cls._load().providers.get(provider, RockyModelProviderCatalog())
        template = cls.find(provider, name) if name else None
        capabilities = {item.name: item for item in catalog.capabilities}
        if template is not None:
            for item in template.capabilities or []:
                capabilities[item.name] = item
        return list(capabilities.values())

    @classmethod
    def recommended(
        cls, provider: RockyModelProviderName
    ) -> Optional[RockyModelTemplate]:
        templates = (
            cls._load()
            .providers.get(
                provider,
                RockyModelProviderCatalog(),
            )
            .models
        )
        for template in templates:
            if template.recommended:
                return template
        return templates[0] if templates else None
