from flut.dart.ui import FontWeight
from flut.flutter.material import Colors, Icons, IconButton, InkWell, Material, Theme
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisSize
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Icon,
    Row,
    SizedBox,
    StatelessWidget,
    Text,
)

from rocky.contracts.model import RockyModelProfile
from rocky.models.templates import RockyModelTemplates
from rocky.system import RockySystem


class RockyModelProfileCard(StatelessWidget):
    def __init__(
        self,
        *,
        profile: RockyModelProfile,
        is_active: bool,
        on_select,
        on_edit,
        on_delete,
        key=None,
    ):
        super().__init__(key=key)
        self.profile = profile
        self.is_active = is_active
        self.on_select = on_select
        self.on_edit = on_edit
        self.on_delete = on_delete

    def _badge(self, label, background, foreground):
        return Container(
            padding=EdgeInsets.symmetric(horizontal=8, vertical=3),
            decoration=BoxDecoration(
                color=background,
                borderRadius=BorderRadius.circular(999),
            ),
            child=Text(
                label,
                style=TextStyle(
                    fontSize=10,
                    fontWeight=FontWeight.w600,
                    color=foreground,
                ),
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        profile = self.profile
        provider_label = RockyModelTemplates.label(profile.provider)
        subtitle = f"{provider_label} \u00b7 {profile.name or '(no model)'}"
        is_selectable = not (
            profile.provider == "litertlm" and not RockySystem.is_litert_lm_installed()
        )

        badges = [
            self._badge(
                provider_label,
                color_scheme.surfaceContainerHighest,
                color_scheme.onSurfaceVariant,
            ),
        ]
        if self.is_active:
            badges.extend(
                [
                    SizedBox(width=6),
                    self._badge(
                        "Active",
                        color_scheme.primary,
                        color_scheme.onPrimary,
                    ),
                ]
            )
        if profile.provider == "litertlm" and not RockySystem.is_litert_lm_installed():
            badges.extend(
                [
                    SizedBox(width=6),
                    self._badge(
                        "LiteRT-LM not installed",
                        color_scheme.errorContainer,
                        color_scheme.onErrorContainer,
                    ),
                ]
            )

        body = Container(
            padding=EdgeInsets.fromLTRB(14, 12, 8, 12),
            child=Row(
                crossAxisAlignment=CrossAxisAlignment.center,
                children=[
                    Expanded(
                        child=Column(
                            crossAxisAlignment=CrossAxisAlignment.start,
                            children=[
                                Row(
                                    mainAxisSize=MainAxisSize.min,
                                    children=badges,
                                ),
                                SizedBox(height=6),
                                Text(
                                    profile.display_name or "Untitled model",
                                    style=TextStyle(
                                        fontSize=14,
                                        fontWeight=FontWeight.w600,
                                        color=color_scheme.onSurface,
                                    ),
                                ),
                                SizedBox(height=2),
                                Text(
                                    subtitle,
                                    style=TextStyle(
                                        fontSize=11,
                                        color=color_scheme.onSurfaceVariant,
                                    ),
                                ),
                            ],
                        ),
                    ),
                    IconButton(
                        onPressed=lambda: self.on_edit(profile.id),
                        icon=Icon(
                            Icons.edit_outlined,
                            size=18,
                            color=color_scheme.onSurfaceVariant,
                        ),
                        tooltip="Edit",
                    ),
                    IconButton(
                        onPressed=lambda: self.on_delete(profile.id),
                        icon=Icon(
                            Icons.delete_outline,
                            size=18,
                            color=color_scheme.onSurfaceVariant,
                        ),
                        tooltip="Delete",
                    ),
                ],
            ),
        )

        return Container(
            margin=EdgeInsets.only(bottom=10),
            decoration=BoxDecoration(
                borderRadius=BorderRadius.circular(10),
                border=Border.all(
                    width=1,
                    color=(
                        color_scheme.primary
                        if self.is_active
                        else color_scheme.outlineVariant
                    ),
                ),
            ),
            child=Material(
                color=Colors.transparent,
                borderRadius=BorderRadius.circular(10),
                child=InkWell(
                    onTap=(
                        (lambda: self.on_select(profile.id)) if is_selectable else None
                    ),
                    borderRadius=BorderRadius.circular(10),
                    hoverColor=color_scheme.onSurface.withOpacity(0.04),
                    child=body,
                ),
            ),
        )
