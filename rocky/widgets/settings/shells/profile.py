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

from rocky.contracts.shell import RockyShellProfile
from rocky.widgets.settings.shells.type_picker import RockyShellTemplates


class RockyShellProfileCard(StatelessWidget):
    def __init__(
        self,
        *,
        profile: RockyShellProfile,
        is_selected: bool,
        on_set_selected,
        on_edit,
        on_delete,
        key=None,
    ):
        super().__init__(key=key)
        self.profile = profile
        self.is_selected = is_selected
        self.on_set_selected = on_set_selected
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
        type_label = RockyShellTemplates.label(profile.shell_type)
        target = RockyShellTemplates.target(profile)
        badges = [
            self._badge(
                type_label,
                color_scheme.surfaceContainerHighest,
                color_scheme.onSurfaceVariant,
            ),
        ]
        if self.is_selected:
            badges.extend(
                [
                    SizedBox(width=6),
                    self._badge(
                        "Selected",
                        color_scheme.primary,
                        color_scheme.onPrimary,
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
                                Row(mainAxisSize=MainAxisSize.min, children=badges),
                                SizedBox(height=6),
                                Text(
                                    profile.display_name or "Untitled environment",
                                    style=TextStyle(
                                        fontSize=14,
                                        fontWeight=FontWeight.w600,
                                        color=color_scheme.onSurface,
                                    ),
                                ),
                                *(
                                    [
                                        SizedBox(height=2),
                                        Text(
                                            target,
                                            style=TextStyle(
                                                fontSize=11,
                                                color=color_scheme.onSurfaceVariant,
                                            ),
                                        ),
                                    ]
                                    if target
                                    else []
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
                        if self.is_selected
                        else color_scheme.outlineVariant
                    ),
                ),
            ),
            child=Material(
                color=Colors.transparent,
                borderRadius=BorderRadius.circular(10),
                child=InkWell(
                    onTap=lambda: self.on_set_selected(
                        profile.id, not self.is_selected
                    ),
                    borderRadius=BorderRadius.circular(10),
                    hoverColor=color_scheme.onSurface.withOpacity(0.04),
                    child=body,
                ),
            ),
        )
