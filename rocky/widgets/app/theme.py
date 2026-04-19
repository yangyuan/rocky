from __future__ import annotations

from typing import Iterable

from flut.dart import Brightness, Color
from flut.flutter.material import ColorScheme, Colors, DynamicSchemeVariant

from rocky.contracts.internal import RockyThemeOption
from rocky.contracts.settings import RockyThemeSettings


class RockyTheme:
    _OPTIONS: tuple[RockyThemeOption, ...] = (
        RockyThemeOption(
            id="default",
            label="Default",
            seed=Color(0xFFB8D4F0),
            variant=DynamicSchemeVariant.neutral,
        ),
        RockyThemeOption(
            id="blue",
            label="Blue",
            seed=Colors.blue,
            variant=DynamicSchemeVariant.tonalSpot,
        ),
        RockyThemeOption(
            id="teal",
            label="Teal",
            seed=Colors.teal,
            variant=DynamicSchemeVariant.tonalSpot,
        ),
        RockyThemeOption(
            id="pink",
            label="Pink",
            seed=Colors.pink,
            variant=DynamicSchemeVariant.tonalSpot,
        ),
        RockyThemeOption(
            id="deepPurple",
            label="Deep Purple",
            seed=Colors.deepPurple,
            variant=DynamicSchemeVariant.tonalSpot,
        ),
        RockyThemeOption(
            id="deepOrange",
            label="Deep Orange",
            seed=Colors.deepOrange,
            variant=DynamicSchemeVariant.tonalSpot,
        ),
    )

    _BY_ID: dict[str, RockyThemeOption] = {opt.id: opt for opt in _OPTIONS}
    _DEFAULT_ID: str = "default"

    def __init__(self):
        raise TypeError("RockyTheme is a static class.")

    @classmethod
    def options(cls) -> Iterable[RockyThemeOption]:
        return cls._OPTIONS

    @classmethod
    def get_option(cls, theme_id: str) -> RockyThemeOption:
        return cls._BY_ID.get(theme_id) or cls._BY_ID[cls._DEFAULT_ID]

    @classmethod
    def build_color_scheme(cls, theme_settings: RockyThemeSettings) -> ColorScheme:
        option = cls.get_option(theme_settings.color)
        brightness = (
            Brightness.dark if theme_settings.brightness == "dark" else Brightness.light
        )

        scheme = ColorScheme.fromSeed(
            seedColor=option.seed,
            brightness=brightness,
            dynamicSchemeVariant=option.variant,
            surfaceTint=Colors.transparent,
        )
        if theme_settings.tint:
            return scheme

        return ColorScheme.fromSeed(
            seedColor=option.seed,
            brightness=brightness,
            dynamicSchemeVariant=option.variant,
            surfaceTint=Colors.transparent,
            surface=cls._desaturate(scheme.surface),
            surfaceDim=cls._desaturate(scheme.surfaceDim),
            surfaceBright=cls._desaturate(scheme.surfaceBright),
            surfaceContainerLowest=cls._desaturate(scheme.surfaceContainerLowest),
            surfaceContainerLow=cls._desaturate(scheme.surfaceContainerLow),
            surfaceContainer=cls._desaturate(scheme.surfaceContainer),
            surfaceContainerHigh=cls._desaturate(scheme.surfaceContainerHigh),
            surfaceContainerHighest=cls._desaturate(scheme.surfaceContainerHighest),
            outline=cls._desaturate(scheme.outline),
            outlineVariant=cls._desaturate(scheme.outlineVariant),
        )

    @staticmethod
    def _srgb_to_linear(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    @staticmethod
    def _linear_to_srgb(c: float) -> int:
        if c <= 0.0031308:
            v = 12.92 * c
        else:
            v = 1.055 * (c ** (1 / 2.4)) - 0.055
        return max(0, min(255, round(v * 255)))

    @classmethod
    def _desaturate(cls, color: Color) -> Color:
        v = color._value
        a = (v >> 24) & 0xFF
        r = (v >> 16) & 0xFF
        g = (v >> 8) & 0xFF
        b = v & 0xFF
        Y = (
            0.2126 * cls._srgb_to_linear(r)
            + 0.7152 * cls._srgb_to_linear(g)
            + 0.0722 * cls._srgb_to_linear(b)
        )
        grey = cls._linear_to_srgb(Y)
        return Color((a << 24) | (grey << 16) | (grey << 8) | grey)
