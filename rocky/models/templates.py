from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rocky.contracts.model import RockyModelProvider, RockyModelTemplate

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "configs" / "models.json"


class RockyModelTemplates:
    PROVIDERS: tuple[RockyModelProvider, ...] = ("openai", "azure_openai", "litertlm")
    LABELS: dict[RockyModelProvider, str] = {
        "openai": "OpenAI",
        "azure_openai": "Azure OpenAI",
        "litertlm": "LiteRT-LM",
    }

    _catalog: Optional[dict[RockyModelProvider, list[RockyModelTemplate]]] = None

    def __init__(self):
        raise TypeError("RockyModelTemplates is a static class.")

    @classmethod
    def _load(cls) -> dict[RockyModelProvider, list[RockyModelTemplate]]:
        if cls._catalog is None:
            raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
            cls._catalog = {
                provider: [
                    RockyModelTemplate(**item) for item in (raw.get(provider) or [])
                ]
                for provider in cls.PROVIDERS
            }
        return cls._catalog

    @classmethod
    def providers(cls) -> tuple[RockyModelProvider, ...]:
        return cls.PROVIDERS

    @classmethod
    def label(cls, provider: RockyModelProvider) -> str:
        return cls.LABELS.get(provider, provider)

    @classmethod
    def all(cls, provider: RockyModelProvider) -> list[RockyModelTemplate]:
        return list(cls._load().get(provider, []))

    @classmethod
    def find(
        cls, provider: RockyModelProvider, name: str
    ) -> Optional[RockyModelTemplate]:
        for template in cls._load().get(provider, []):
            if template.name == name:
                return template
        return None

    @classmethod
    def recommended(cls, provider: RockyModelProvider) -> Optional[RockyModelTemplate]:
        templates = cls._load().get(provider, [])
        for template in templates:
            if template.recommended:
                return template
        return templates[0] if templates else None
