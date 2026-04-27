from __future__ import annotations

from rocky.contracts.model import (
    RockyModelCapability,
    RockyModelCapabilityDefinition,
    RockyModelCapabilityName,
    RockyModelCapabilityType,
    RockyModelCapabilityValue,
    RockyModelProfile,
    RockyModelProviderName,
)
from rocky.models.templates import RockyModelTemplates


class RockyModelCapabilities:
    def __init__(self):
        raise TypeError("RockyModelCapabilities is a static class.")

    @classmethod
    def find(
        cls,
        capabilities: list[RockyModelCapability],
        name: RockyModelCapabilityName,
    ) -> RockyModelCapability | None:
        for capability in capabilities:
            if capability.name == name:
                return capability
        return None

    @classmethod
    def value(
        cls,
        capabilities: list[RockyModelCapability],
        name: RockyModelCapabilityName,
    ) -> RockyModelCapabilityValue | None:
        capability = cls.find(capabilities, name)
        if capability is None:
            return None
        return capability.value

    @classmethod
    def definitions(cls) -> list[RockyModelCapabilityDefinition]:
        return RockyModelTemplates.capability_definitions()

    @classmethod
    def definition(
        cls,
        name: RockyModelCapabilityName,
    ) -> RockyModelCapabilityDefinition | None:
        for definition in cls.definitions():
            if definition.name == name:
                return definition
        return None

    @classmethod
    def label(cls, name: RockyModelCapabilityName) -> str:
        definition = cls.definition(name)
        if definition is None:
            return name.value
        return definition.label

    @classmethod
    def baseline(
        cls,
        provider: RockyModelProviderName,
        name: str,
    ) -> list[RockyModelCapability]:
        values = {
            definition.name: definition.default
            for definition in RockyModelTemplates.capability_definitions()
        }
        for capability in RockyModelTemplates.capability_overrides(provider, name):
            values[capability.name] = capability.value
        return [
            RockyModelCapability(name=definition.name, value=values[definition.name])
            for definition in RockyModelTemplates.capability_definitions()
        ]

    @classmethod
    def effective(cls, profile: RockyModelProfile | None) -> list[RockyModelCapability]:
        if profile is None:
            return []
        values = {
            capability.name: capability.value for capability in profile.capabilities
        }
        result: list[RockyModelCapability] = []
        for capability in cls.baseline(profile.provider, profile.name):
            result.append(
                RockyModelCapability(
                    name=capability.name,
                    value=values.get(capability.name, capability.value),
                )
            )
        return result

    @classmethod
    def profile_overrides(
        cls,
        *,
        provider: RockyModelProviderName,
        name: str,
        capabilities: list[RockyModelCapability],
    ) -> list[RockyModelCapability]:
        baseline = {
            capability.name: capability.value
            for capability in cls.baseline(provider, name)
        }
        overrides: list[RockyModelCapability] = []
        for capability in capabilities:
            if baseline.get(capability.name) != capability.value:
                overrides.append(capability)
        return overrides

    @classmethod
    def bool_value(
        cls,
        capabilities: list[RockyModelCapability],
        name: RockyModelCapabilityName,
    ) -> bool:
        value = cls.value(capabilities, name)
        if isinstance(value, bool):
            return value
        return False

    @classmethod
    def typed_value(
        cls,
        definition: RockyModelCapabilityDefinition,
        value: RockyModelCapabilityValue,
    ) -> RockyModelCapabilityValue:
        if definition.type == RockyModelCapabilityType.BOOL:
            return value if isinstance(value, bool) else bool(value)
        if definition.type == RockyModelCapabilityType.INTEGER:
            return (
                value
                if isinstance(value, int) and not isinstance(value, bool)
                else int(value)
            )
        if definition.type == RockyModelCapabilityType.FLOAT:
            return value if isinstance(value, float) else float(value)
        return str(value)

    @classmethod
    def with_value(
        cls,
        capabilities: list[RockyModelCapability],
        name: RockyModelCapabilityName,
        value: RockyModelCapabilityValue,
    ) -> list[RockyModelCapability]:
        updated = RockyModelCapability(name=name, value=value)
        result: list[RockyModelCapability] = []
        replaced = False
        for capability in capabilities:
            if capability.name == name:
                result.append(updated)
                replaced = True
            else:
                result.append(capability)
        if not replaced:
            result.append(updated)
        return result

    @classmethod
    def supports_function(cls, profile: RockyModelProfile | None) -> bool:
        if profile is None:
            return False
        return cls.bool_value(
            cls.effective(profile),
            RockyModelCapabilityName.FUNCTION,
        )
