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

from rocky.contracts.shell import RockyShellProfile, RockyShellType


class RockyShellTemplates:
    @classmethod
    def all(cls) -> list[RockyShellType]:
        return [
            "docker",
            "ssh",
            "wsl",
            "docker_in_wsl",
            "docker_over_ssh",
        ]

    @classmethod
    def label(cls, shell_type: RockyShellType) -> str:
        labels: dict[RockyShellType, str] = {
            "docker": "Docker",
            "docker_in_wsl": "Docker in WSL",
            "docker_over_ssh": "Docker over SSH",
            "ssh": "SSH",
            "wsl": "WSL",
        }
        return labels[shell_type]

    @classmethod
    def requires_name(cls, shell_type: RockyShellType) -> bool:
        return shell_type in ("docker", "docker_in_wsl", "docker_over_ssh")

    @classmethod
    def uses_host(cls, shell_type: RockyShellType) -> bool:
        return shell_type in ("ssh", "wsl", "docker_over_ssh", "docker_in_wsl")

    @classmethod
    def requires_host(cls, shell_type: RockyShellType) -> bool:
        return shell_type in ("ssh", "docker_over_ssh")

    @classmethod
    def host_label(cls, shell_type: RockyShellType) -> str:
        if shell_type in ("wsl", "docker_in_wsl"):
            return "WSL distribution"
        return "Host"

    @classmethod
    def host_hint(cls, shell_type: RockyShellType) -> str:
        if shell_type in ("wsl", "docker_in_wsl"):
            return "Ubuntu"
        return "user@example.com"

    @classmethod
    def target(cls, profile: RockyShellProfile) -> str:
        shell_type = profile.shell_type
        if cls.requires_name(shell_type) and profile.name:
            return profile.name
        if cls.uses_host(shell_type) and profile.host:
            return profile.host
        if shell_type == "wsl":
            return ""
        return "not configured"


class RockyShellTypePicker(StatelessWidget):
    def __init__(
        self,
        *,
        value: RockyShellType,
        on_changed,
        key=None,
    ):
        super().__init__(key=key)
        self.value = value
        self.on_changed = on_changed

    def _chip(self, color_scheme, shell_type: RockyShellType):
        selected = shell_type == self.value
        radius = BorderRadius.circular(8)
        background = color_scheme.primary if selected else Colors.transparent
        foreground = color_scheme.onPrimary if selected else color_scheme.onSurface
        border_color = color_scheme.primary if selected else color_scheme.outlineVariant
        return Material(
            color=background,
            borderRadius=radius,
            child=InkWell(
                onTap=lambda: self.on_changed(shell_type),
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.04),
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=12, vertical=8),
                    decoration=BoxDecoration(
                        borderRadius=radius,
                        border=Border.all(width=1, color=border_color),
                    ),
                    child=Text(
                        RockyShellTemplates.label(shell_type),
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
            children=[
                self._chip(color_scheme, shell_type)
                for shell_type in RockyShellTemplates.all()
            ],
        )
