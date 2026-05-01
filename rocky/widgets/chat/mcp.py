from __future__ import annotations

from typing import Callable

from flut.dart.ui import FontWeight
from flut.flutter.material import (
    Checkbox,
    Colors,
    Dialog,
    Icons,
    InkWell,
    Material,
    TextButton,
    Theme,
    showDialog,
)
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment, MainAxisSize
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Icon,
    Row,
    SingleChildScrollView,
    SizedBox,
    State,
    StatefulWidget,
    Text,
)
from flut.flutter.widgets.navigator import Navigator

from rocky.contracts.mcp import RockyMcpServerProfile
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.mcp.type_picker import RockyMcpTemplates


class RockyChatMcpDialog(StatefulWidget):
    def __init__(
        self,
        *,
        mcp_server_profiles: list[RockyMcpServerProfile],
        selected_mcp_server_ids: list[str],
        on_set_mcp_server_selected: Callable[[str, bool], None],
        on_open_settings: Callable[[], None],
        key=None,
    ):
        super().__init__(key=key)
        self.mcp_server_profiles = list(mcp_server_profiles)
        self.selected_mcp_server_ids = list(selected_mcp_server_ids)
        self.on_set_mcp_server_selected = on_set_mcp_server_selected
        self.on_open_settings = on_open_settings

    @staticmethod
    def open(
        context,
        *,
        mcp_server_profiles: list[RockyMcpServerProfile],
        selected_mcp_server_ids: list[str],
        on_set_mcp_server_selected: Callable[[str, bool], None],
        on_open_settings: Callable[[], None],
    ) -> None:
        def _builder(dialog_context):
            def _open_settings():
                Navigator.pop(dialog_context)
                on_open_settings()

            return Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=RockyChatMcpDialog(
                    mcp_server_profiles=mcp_server_profiles,
                    selected_mcp_server_ids=selected_mcp_server_ids,
                    on_set_mcp_server_selected=on_set_mcp_server_selected,
                    on_open_settings=_open_settings,
                ),
            )

        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=_builder,
        )

    def createState(self):
        return _RockyChatMcpDialogState()


class _RockyChatMcpDialogState(State[RockyChatMcpDialog]):
    def initState(self):
        self._selected_mcp_server_ids = list(self.widget.selected_mcp_server_ids)

    def _toggle(self, profile: RockyMcpServerProfile, selected: bool) -> None:
        ids = list(self._selected_mcp_server_ids)
        already_selected = profile.id in ids
        if selected and not already_selected:
            ids.append(profile.id)
        elif not selected and already_selected:
            ids = [
                mcp_server_id for mcp_server_id in ids if mcp_server_id != profile.id
            ]
        else:
            return

        def _apply():
            self._selected_mcp_server_ids = ids

        self.setState(_apply)
        self.widget.on_set_mcp_server_selected(profile.id, selected)

    def _row(self, color_scheme, profile: RockyMcpServerProfile):
        selected = profile.id in self._selected_mcp_server_ids
        radius = BorderRadius.circular(8)
        target = RockyMcpTemplates.target(profile)
        subtitle = RockyMcpTemplates.label(profile.server_type)
        if target:
            subtitle = f"{subtitle} - {target}"
        return Material(
            color=color_scheme.surfaceContainerLowest,
            borderRadius=radius,
            child=InkWell(
                onTap=lambda: self._toggle(profile, not selected),
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.04),
                child=Container(
                    padding=EdgeInsets.fromLTRB(8, 8, 12, 8),
                    decoration=BoxDecoration(
                        borderRadius=radius,
                        border=Border.all(width=1, color=color_scheme.outlineVariant),
                    ),
                    child=Row(
                        mainAxisSize=MainAxisSize.max,
                        children=[
                            Checkbox(
                                value=selected,
                                onChanged=lambda value: self._toggle(
                                    profile, bool(value)
                                ),
                            ),
                            SizedBox(width=8),
                            Expanded(
                                child=Column(
                                    crossAxisAlignment=CrossAxisAlignment.start,
                                    children=[
                                        Text(
                                            RockyMcpTemplates.display_name(profile),
                                            style=TextStyle(
                                                fontSize=13,
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
                                )
                            ),
                        ],
                    ),
                ),
            ),
        )

    def _settings_button(self, color_scheme):
        return TextButton(
            onPressed=self.widget.on_open_settings,
            child=Row(
                mainAxisSize=MainAxisSize.min,
                children=[
                    Icon(Icons.settings, size=16, color=color_scheme.onSurfaceVariant),
                    SizedBox(width=6),
                    Text(
                        "Settings",
                        style=TextStyle(
                            fontSize=13,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                ],
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        children = []
        if self.widget.mcp_server_profiles:
            for profile in self.widget.mcp_server_profiles:
                children.append(self._row(color_scheme, profile))
                children.append(SizedBox(height=8))
        else:
            children.append(
                Text(
                    "No MCP servers configured.",
                    style=TextStyle(fontSize=12, color=color_scheme.onSurfaceVariant),
                )
            )
        body = Container(
            width=460,
            height=320,
            padding=EdgeInsets.all(16),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=[
                    Expanded(
                        child=SingleChildScrollView(
                            child=Column(
                                crossAxisAlignment=CrossAxisAlignment.stretch,
                                children=children,
                            )
                        )
                    ),
                    SizedBox(height=12),
                    Row(
                        mainAxisAlignment=MainAxisAlignment.end,
                        children=[self._settings_button(color_scheme)],
                    ),
                ],
            ),
        )
        return RockyDialog(
            title="MCP Servers",
            leading_icon=Icons.hub_outlined,
            mode="fit_content",
            body=body,
        )
