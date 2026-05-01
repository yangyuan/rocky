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

from rocky.contracts.mcp import RockyMcpServerProfile
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.mcp.delete_dialog import RockyMcpDeleteDialog
from rocky.widgets.settings.mcp.profile import RockyMcpProfileCard
from rocky.widgets.settings.mcp.profile_editor import RockyMcpProfileEditor
from rocky.widgets.settings.mcp.type_picker import RockyMcpTemplates


class RockySettingsMcpPage(StatefulWidget):
    def __init__(
        self,
        *,
        mcp_server_profiles,
        default_mcp_server_ids,
        on_add_mcp_server_profile,
        on_update_mcp_server_profile,
        on_delete_mcp_server_profile,
        on_set_default_mcp_server_selected,
        key=None,
    ):
        super().__init__(key=key)
        self.mcp_server_profiles = mcp_server_profiles
        self.default_mcp_server_ids = default_mcp_server_ids or []
        self.on_add_mcp_server_profile = on_add_mcp_server_profile
        self.on_update_mcp_server_profile = on_update_mcp_server_profile
        self.on_delete_mcp_server_profile = on_delete_mcp_server_profile
        self.on_set_default_mcp_server_selected = on_set_default_mcp_server_selected

    def createState(self):
        return _RockySettingsMcpPageState()


class _RockySettingsMcpPageState(State[RockySettingsMcpPage]):
    def _open_add(self):
        self._open_editor(initial=None)

    def _open_edit(self, mcp_server_id: str):
        profile = next(
            (
                profile
                for profile in (self.widget.mcp_server_profiles or [])
                if profile.id == mcp_server_id
            ),
            None,
        )
        if profile is None:
            return
        self._open_editor(initial=profile)

    def _open_editor(self, *, initial: RockyMcpServerProfile | None):
        context = self.context

        def _editor_body(builder_context):
            screen_height = MediaQuery.of(builder_context).size.height
            max_height = max(300.0, screen_height - 160.0)
            return ConstrainedBox(
                constraints=BoxConstraints(maxHeight=max_height, maxWidth=620),
                child=SingleChildScrollView(
                    padding=EdgeInsets.all(8),
                    child=Container(
                        width=580,
                        child=RockyMcpProfileEditor(
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
                        "Edit MCP server" if initial is not None else "Add MCP server"
                    ),
                    leading_icon=Icons.hub_outlined,
                    mode="fit_content",
                    on_close=lambda: Navigator.pop(dialog_context),
                    body=Builder(builder=_editor_body),
                ),
            ),
        )

    def _on_save(self, profile: RockyMcpServerProfile, *, is_edit: bool):
        if is_edit:
            self.widget.on_update_mcp_server_profile(profile)
        else:
            self.widget.on_add_mcp_server_profile(profile)

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
                                "Add MCP server",
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
        profiles = self.widget.mcp_server_profiles or []
        children = [
            Text(
                "MCP Servers",
                style=TextStyle(
                    fontSize=18,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurface,
                ),
            ),
            SizedBox(height=16),
        ]
        for profile in profiles:
            children.append(
                RockyMcpProfileCard(
                    profile=profile,
                    is_default=profile.id in self.widget.default_mcp_server_ids,
                    on_set_default=self.widget.on_set_default_mcp_server_selected,
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

    def _confirm_delete(self, mcp_server_id: str):
        profile = next(
            (
                candidate
                for candidate in (self.widget.mcp_server_profiles or [])
                if candidate.id == mcp_server_id
            ),
            None,
        )
        if profile is None:
            return
        label = RockyMcpTemplates.display_name(profile)
        showDialog(
            context=self.context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=RockyMcpDeleteDialog(
                    label=label,
                    on_cancel=lambda: Navigator.pop(dialog_context),
                    on_confirm=lambda: (
                        Navigator.pop(dialog_context),
                        self.widget.on_delete_mcp_server_profile(mcp_server_id),
                    ),
                ),
            ),
        )
