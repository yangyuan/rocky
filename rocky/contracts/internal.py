from __future__ import annotations

from flut.dart import Color
from flut.flutter.material import DynamicSchemeVariant


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
