from flut.dart.ui import FontWeight
from flut.flutter.foundation import ValueKey
from flut.flutter.material import Colors, Icons, InkWell, Material, Theme
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BorderSide,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment
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
    StatelessWidget,
    Text,
)

from rocky.chats import RockyChats
from rocky.settings import RockySettings
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.chats.page import RockySettingsChatsPage
from rocky.widgets.settings.mcp.page import RockySettingsMcpPage
from rocky.widgets.settings.models.page import RockySettingsModelsPage
from rocky.widgets.settings.skills.page import RockySettingsSkillsPage
from rocky.widgets.settings.shells.page import RockySettingsShellsPage


class _NavigationRow(StatelessWidget):
    def __init__(self, *, icon, label, is_selected, onTap, key=None):
        super().__init__(key=key)
        self.icon = icon
        self.label = label
        self.is_selected = is_selected
        self.onTap = onTap

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        if self.is_selected:
            background = color_scheme.secondaryContainer
            foreground = color_scheme.onSecondaryContainer
            border_color = color_scheme.primary
        else:
            background = Colors.transparent
            foreground = color_scheme.onSurface
            border_color = Colors.transparent

        return Material(
            color=Colors.transparent,
            child=InkWell(
                onTap=self.onTap,
                borderRadius=BorderRadius.circular(6),
                hoverColor=color_scheme.onSurface.withOpacity(0.08),
                child=Container(
                    margin=EdgeInsets.only(bottom=4),
                    padding=EdgeInsets.fromLTRB(10, 8, 10, 8),
                    decoration=BoxDecoration(
                        color=background,
                        borderRadius=BorderRadius.circular(6),
                        border=Border.all(width=1, color=border_color),
                    ),
                    child=Row(
                        children=[
                            Icon(self.icon, size=16, color=foreground),
                            SizedBox(width=10),
                            Text(
                                self.label,
                                style=TextStyle(
                                    fontSize=13,
                                    fontWeight=FontWeight.w600,
                                    color=foreground,
                                ),
                            ),
                        ],
                    ),
                ),
            ),
        )


class RockySettingsDialog(StatefulWidget):
    def __init__(
        self,
        *,
        settings: RockySettings,
        chats: RockyChats,
        initial_page: str = "models",
        on_close=None,
        key=None,
    ):
        super().__init__(key=key)
        self.settings = settings
        self.chats = chats
        self.initial_page = initial_page
        self.on_close = on_close

    def createState(self):
        return _RockySettingsDialogState()


class _RockySettingsDialogState(State[RockySettingsDialog]):
    def initState(self):
        self.page = self.widget.initial_page
        self.widget.settings.addListener(self._on_settings_changed)

    def dispose(self):
        self.widget.settings.removeListener(self._on_settings_changed)

    def _on_settings_changed(self):
        self.setState(lambda: None)

    def _set_page(self, name):
        def _apply():
            self.page = name

        self.setState(_apply)

    def _navigation_column(self, color_scheme):
        return Container(
            width=180,
            padding=EdgeInsets.fromLTRB(10, 12, 10, 12),
            decoration=BoxDecoration(
                border=Border(
                    right=BorderSide(width=1, color=color_scheme.outlineVariant)
                ),
            ),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=[
                    _NavigationRow(
                        icon=Icons.rocket_launch_outlined,
                        label="Models",
                        is_selected=self.page == "models",
                        onTap=lambda: self._set_page("models"),
                    ),
                    _NavigationRow(
                        icon=Icons.storage,
                        label="Environments",
                        is_selected=self.page == "shells",
                        onTap=lambda: self._set_page("shells"),
                    ),
                    _NavigationRow(
                        icon=Icons.extension,
                        label="Skills",
                        is_selected=self.page == "skills",
                        onTap=lambda: self._set_page("skills"),
                    ),
                    _NavigationRow(
                        icon=Icons.hub_outlined,
                        label="MCP",
                        is_selected=self.page == "mcp",
                        onTap=lambda: self._set_page("mcp"),
                    ),
                    _NavigationRow(
                        icon=Icons.chat_bubble_outline,
                        label="Chats",
                        is_selected=self.page == "chats",
                        onTap=lambda: self._set_page("chats"),
                    ),
                ],
            ),
        )

    def _models_body(self):
        settings = self.widget.settings
        return RockySettingsModelsPage(
            key=ValueKey("settings-models"),
            model_profiles=settings.model_profiles,
            default_model_profile_id=settings.default_model_profile_id,
            on_add_model_profile=settings.add_model_profile,
            on_update_model_profile=settings.update_model_profile,
            on_delete_model_profile=settings.delete_model_profile,
            on_set_default_model_profile=settings.set_default_model_profile,
        )

    def _shells_body(self):
        settings = self.widget.settings
        return RockySettingsShellsPage(
            key=ValueKey("settings-shells"),
            shell_profiles=settings.shell_profiles,
            default_shell_profile_ids=settings.default_shell_profile_ids,
            on_add_shell_profile=settings.add_shell_profile,
            on_update_shell_profile=settings.update_shell_profile,
            on_delete_shell_profile=settings.delete_shell_profile,
            on_set_default_shell_profile_selected=settings.set_default_shell_profile_selected,
        )

    def _skills_body(self):
        settings = self.widget.settings
        return RockySettingsSkillsPage(
            key=ValueKey("settings-skills"),
            skills=settings.skills,
            default_skill_ids=settings.default_skill_ids,
            system_skills_folder=settings.system_skills_folder,
            user_skills_folder=settings.user_skills_folder,
            on_set_default_skill_selected=settings.set_default_skill_selected,
        )

    def _mcp_body(self):
        settings = self.widget.settings
        return RockySettingsMcpPage(
            key=ValueKey("settings-mcp"),
            mcp_server_profiles=settings.mcp_server_profiles,
            default_mcp_server_ids=settings.default_mcp_server_ids,
            on_add_mcp_server_profile=settings.add_mcp_server_profile,
            on_update_mcp_server_profile=settings.update_mcp_server_profile,
            on_delete_mcp_server_profile=settings.delete_mcp_server_profile,
            on_set_default_mcp_server_selected=settings.set_default_mcp_server_selected,
        )

    def _body(self):
        if self.page == "chats":
            return RockySettingsChatsPage(
                key=ValueKey("settings-chats"),
                settings=self.widget.settings,
                chats=self.widget.chats,
            )
        if self.page == "shells":
            return self._shells_body()
        if self.page == "skills":
            return self._skills_body()
        if self.page == "mcp":
            return self._mcp_body()
        return self._models_body()

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme

        layout = Row(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=[
                self._navigation_column(color_scheme),
                Expanded(
                    child=SingleChildScrollView(
                        padding=EdgeInsets.all(20),
                        child=self._body(),
                    ),
                ),
            ],
        )

        return RockyDialog(
            title="Settings",
            leading_icon=Icons.settings,
            on_close=self.widget.on_close,
            body=layout,
        )
