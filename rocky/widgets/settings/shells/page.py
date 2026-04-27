from flut.dart.ui import FontWeight
from flut.flutter.material import (
    Colors,
    Dialog,
    Icons,
    InkWell,
    Material,
    Theme,
    showDialog,
)
from flut.flutter.painting import BorderRadius, EdgeInsets, TextStyle
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment, MainAxisSize
from flut.flutter.rendering.box import BoxConstraints
from flut.flutter.widgets import (
    Builder,
    Column,
    ConstrainedBox,
    Container,
    Icon,
    Row,
    SingleChildScrollView,
    SizedBox,
    State,
    StatefulWidget,
    Text,
)
from flut.flutter.widgets.media_query import MediaQuery
from flut.flutter.widgets.navigator import Navigator

from rocky.contracts.shell import RockyShellProfile
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.shells.delete_dialog import RockyShellDeleteDialog
from rocky.widgets.settings.shells.profile import RockyShellProfileCard
from rocky.widgets.settings.shells.profile_editor import RockyShellProfileEditor


class RockySettingsShellsPage(StatefulWidget):
    def __init__(
        self,
        *,
        shells,
        selected_shell_ids,
        on_add_shell,
        on_update_shell,
        on_delete_shell,
        on_set_shell_selected,
        key=None,
    ):
        super().__init__(key=key)
        self.shells = shells
        self.selected_shell_ids = selected_shell_ids or []
        self.on_add_shell = on_add_shell
        self.on_update_shell = on_update_shell
        self.on_delete_shell = on_delete_shell
        self.on_set_shell_selected = on_set_shell_selected

    def createState(self):
        return _RockySettingsShellsPageState()


class _RockySettingsShellsPageState(State[RockySettingsShellsPage]):
    def _open_add(self):
        self._open_editor(initial=None)

    def _open_edit(self, shell_id: str):
        profile = next(
            (shell for shell in (self.widget.shells or []) if shell.id == shell_id),
            None,
        )
        if profile is None:
            return
        self._open_editor(initial=profile)

    def _open_editor(self, *, initial: RockyShellProfile | None):
        context = self.context

        def _editor_body(builder_context):
            screen_height = MediaQuery.of(builder_context).size.height
            max_height = max(280.0, screen_height - 160.0)
            return ConstrainedBox(
                constraints=BoxConstraints(maxHeight=max_height, maxWidth=560),
                child=SingleChildScrollView(
                    padding=EdgeInsets.all(8),
                    child=Container(
                        width=520,
                        child=RockyShellProfileEditor(
                            initial=initial,
                            on_save=lambda profile: (
                                Navigator.pop(builder_context),
                                self._on_save(profile, is_edit=initial is not None),
                            ),
                            on_cancel=lambda: Navigator.pop(builder_context),
                        ),
                    ),
                ),
            )

        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=RockyDialog(
                    title=(
                        "Edit environment" if initial is not None else "Add environment"
                    ),
                    leading_icon=(
                        Icons.edit_outlined if initial is not None else Icons.add
                    ),
                    mode="fit_content",
                    on_close=lambda: Navigator.pop(dialog_context),
                    body=Builder(builder=_editor_body),
                ),
            ),
        )

    def _on_save(self, profile: RockyShellProfile, *, is_edit: bool):
        if is_edit:
            self.widget.on_update_shell(profile)
        else:
            self.widget.on_add_shell(profile)

    def _add_button(self, color_scheme):
        radius = BorderRadius.circular(8)
        return Material(
            color=color_scheme.primaryContainer,
            borderRadius=radius,
            child=InkWell(
                onTap=self._open_add,
                borderRadius=radius,
                hoverColor=color_scheme.onPrimaryContainer.withOpacity(0.06),
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=12, vertical=7),
                    child=Row(
                        mainAxisSize=MainAxisSize.min,
                        children=[
                            Icon(
                                Icons.add,
                                size=14,
                                color=color_scheme.onPrimaryContainer,
                            ),
                            SizedBox(width=6),
                            Text(
                                "Add environment",
                                style=TextStyle(
                                    fontSize=13,
                                    fontWeight=FontWeight.w500,
                                    color=color_scheme.onPrimaryContainer,
                                ),
                            ),
                        ],
                    ),
                ),
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        shells = self.widget.shells or []
        children = [
            Text(
                "Environments",
                style=TextStyle(
                    fontSize=18,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurface,
                ),
            ),
            SizedBox(height=4),
            Text(
                (
                    "Environments are Docker instances, remote SSH servers, or other shell access points Rocky can use to execute commands."
                ),
                style=TextStyle(fontSize=12, color=color_scheme.onSurfaceVariant),
            ),
            SizedBox(height=16),
        ]
        for shell in shells:
            children.append(
                RockyShellProfileCard(
                    profile=shell,
                    is_selected=shell.id in self.widget.selected_shell_ids,
                    on_set_selected=self.widget.on_set_shell_selected,
                    on_edit=self._open_edit,
                    on_delete=self._confirm_delete,
                )
            )
        children.append(SizedBox(height=4))
        children.append(
            Row(
                mainAxisAlignment=MainAxisAlignment.end,
                children=[self._add_button(color_scheme)],
            )
        )
        return Column(crossAxisAlignment=CrossAxisAlignment.stretch, children=children)

    def _confirm_delete(self, shell_id: str):
        profile = next(
            (shell for shell in (self.widget.shells or []) if shell.id == shell_id),
            None,
        )
        if profile is None:
            return
        label = profile.display_name or "this environment"
        showDialog(
            context=self.context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=RockyShellDeleteDialog(
                    label=label,
                    on_cancel=lambda: Navigator.pop(dialog_context),
                    on_confirm=lambda: (
                        Navigator.pop(dialog_context),
                        self.widget.on_delete_shell(shell_id),
                    ),
                ),
            ),
        )
