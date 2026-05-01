from flut.dart.ui import FontWeight
from flut.flutter.material import Colors, InkWell, Material, Theme
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.widgets import Container, StatelessWidget, Text, Wrap

from rocky.contracts.mcp import (
    RockyHttpMcpServerProperties,
    RockyMcpServerProfile,
    RockyMcpServerType,
    RockyStdioMcpServerProperties,
)


class RockyMcpTemplates:
    _LABELS: dict[RockyMcpServerType, str] = {
        RockyMcpServerType.STDIO: "STDIO",
        RockyMcpServerType.HTTP: "HTTP",
    }

    @classmethod
    def all(cls) -> list[RockyMcpServerType]:
        return [RockyMcpServerType.STDIO, RockyMcpServerType.HTTP]

    @classmethod
    def label(cls, server_type: RockyMcpServerType) -> str:
        return cls._LABELS[server_type]

    @classmethod
    def target(cls, profile: RockyMcpServerProfile) -> str:
        properties = profile.properties
        if isinstance(properties, RockyStdioMcpServerProperties):
            return properties.command
        if isinstance(properties, RockyHttpMcpServerProperties):
            return properties.url
        return ""

    @classmethod
    def derived_display_name(cls, profile: RockyMcpServerProfile) -> str:
        return cls.derived_display_name_for(
            profile.server_type,
            cls.target(profile),
        )

    @classmethod
    def derived_display_name_for(
        cls,
        server_type: RockyMcpServerType,
        target: str,
    ) -> str:
        label = cls._LABELS[server_type]
        target = (target or "").strip()
        if not target:
            return label
        return f"{label} {target}"

    @classmethod
    def display_name(cls, profile: RockyMcpServerProfile) -> str:
        explicit = (profile.display_name or "").strip()
        if explicit:
            return explicit
        return cls.derived_display_name(profile)


class RockyMcpTypePicker(StatelessWidget):
    def __init__(self, *, value: RockyMcpServerType, on_changed, key=None):
        super().__init__(key=key)
        self.value = value
        self.on_changed = on_changed

    def _chip(self, color_scheme, server_type: RockyMcpServerType):
        selected = server_type == self.value
        radius = BorderRadius.circular(8)
        background = color_scheme.primary if selected else Colors.transparent
        foreground = color_scheme.onPrimary if selected else color_scheme.onSurface
        border_color = color_scheme.primary if selected else color_scheme.outlineVariant
        return Material(
            color=background,
            borderRadius=radius,
            child=InkWell(
                onTap=lambda: self.on_changed(server_type),
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.04),
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=12, vertical=8),
                    decoration=BoxDecoration(
                        borderRadius=radius,
                        border=Border.all(width=1, color=border_color),
                    ),
                    child=Text(
                        RockyMcpTemplates.label(server_type),
                        style=TextStyle(
                            fontSize=13,
                            fontWeight=FontWeight.w500,
                            color=foreground,
                        ),
                    ),
                ),
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        return Wrap(
            spacing=8,
            runSpacing=8,
            children=[self._chip(color_scheme, item) for item in self.all_types()],
        )

    def all_types(self) -> list[RockyMcpServerType]:
        return RockyMcpTemplates.all()
