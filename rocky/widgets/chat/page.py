import os

from flut.dart.ui import FontWeight, TextAlign
from flut.flutter.material import (
    Colors,
    CircularProgressIndicator,
    Icons,
    InkWell,
    Material,
    PopupMenuButton,
    PopupMenuItem,
    Theme,
    Tooltip,
)
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment, MainAxisSize
from flut.flutter.rendering.box import BoxConstraints
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Icon,
    Row,
    SizedBox,
    State,
    StatefulWidget,
    StatelessWidget,
    Text,
)

from rocky.contracts.agent import RockyAgentStatus
from rocky.contracts.model import RockyModelCapabilityName, RockyModelProviderName
from rocky.models.capabilities import RockyModelCapabilities
from rocky.models.templates import RockyModelTemplates
from rocky.system import RockySystem
from rocky.widgets.chat.composer import RockyChatComposer
from rocky.widgets.chat.messages import RockyChatMessageList
from rocky.widgets.settings.shells.type_picker import RockyShellTemplates


class RockyChatHeader(StatelessWidget):
    _MENU_ITEM_MODEL_MANAGE = "__manage__"
    _MENU_ITEM_SHELL_MANAGE = "__manage_shell__"
    _MENU_WIDTH = 200

    def __init__(
        self,
        *,
        profiles,
        selected_profile_id,
        on_select_profile,
        shells,
        selected_shell_ids,
        on_set_shell_selected,
        on_open_model_manager,
        on_open_shell_manager,
        key=None,
    ):
        super().__init__(key=key)
        self.profiles = profiles or []
        self.selected_profile_id = selected_profile_id
        self.on_select_profile = on_select_profile
        self.shells = shells or []
        self.selected_shell_ids = selected_shell_ids or []
        self.on_set_shell_selected = on_set_shell_selected
        self.on_open_model_manager = on_open_model_manager
        self.on_open_shell_manager = on_open_shell_manager

    def _selected_label(self):
        for profile in self.profiles:
            if profile.id == self.selected_profile_id:
                return profile.display_name or "Untitled model"
        return "No model"

    def _environment_label(self):
        if not self.shells:
            return "No environments"
        selected = self._selected_shells()
        count = len(selected)
        if count == 0:
            return "No environment selected"
        if count == 1:
            return selected[0].display_name or "Untitled environment"
        return f"{count} environments"

    def _selected_shells(self):
        selected_ids = set(self.selected_shell_ids)
        return [shell for shell in self.shells if shell.id in selected_ids]

    def _selected_profile(self):
        for profile in self.profiles:
            if profile.id == self.selected_profile_id:
                return profile
        return None

    def _shell_disabled_reason(self) -> str | None:
        profile = self._selected_profile()
        if profile is None:
            return "Select a model to use environments."
        if not RockyModelCapabilities.supports_function(profile):
            label = RockyModelCapabilities.label(RockyModelCapabilityName.FUNCTION)
            return f"Environment requires model's {label} capability."
        return None

    def _on_selected(self, context, value):
        if value == self._MENU_ITEM_MODEL_MANAGE:
            self.on_open_model_manager()
            return
        self.on_select_profile(value)

    def _on_shell_selected(self, context, value):
        if value == self._MENU_ITEM_SHELL_MANAGE:
            self.on_open_shell_manager()
            return
        selected = value in self.selected_shell_ids
        self.on_set_shell_selected(value, not selected)

    @staticmethod
    def _profile_model_text(profile) -> str:
        name = (profile.name or "").strip()
        if not name:
            return "(no model)"
        if profile.provider == RockyModelProviderName.LITERTLM:
            return os.path.basename(name) or name
        return name

    def _menu_item(self, color_scheme, profile):
        provider_label = RockyModelTemplates.label(profile.provider)
        is_active = profile.id == self.selected_profile_id
        is_disabled = (
            profile.provider == RockyModelProviderName.LITERTLM
            and not RockySystem.is_litert_lm_installed()
        )
        model_text = self._profile_model_text(profile)
        title_color = (
            color_scheme.onSurface.withOpacity(0.4)
            if is_disabled
            else color_scheme.onSurface
        )
        subtitle_color = (
            color_scheme.onSurfaceVariant.withOpacity(0.5)
            if is_disabled
            else color_scheme.onSurfaceVariant
        )
        return PopupMenuItem(
            value=profile.id,
            enabled=not is_disabled,
            height=44,
            child=Row(
                mainAxisSize=MainAxisSize.max,
                children=[
                    Icon(
                        Icons.check if is_active else Icons.circle,
                        size=14,
                        color=(
                            color_scheme.primary if is_active else Colors.transparent
                        ),
                    ),
                    SizedBox(width=8),
                    Expanded(
                        child=Column(
                            crossAxisAlignment=CrossAxisAlignment.start,
                            children=[
                                Text(
                                    profile.display_name or "Untitled model",
                                    style=TextStyle(
                                        fontSize=13,
                                        fontWeight=FontWeight.w600,
                                        color=title_color,
                                    ),
                                ),
                                Text(
                                    f"{provider_label} \u00b7 {model_text}",
                                    style=TextStyle(
                                        fontSize=11,
                                        color=subtitle_color,
                                    ),
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _item_builder(self, context):
        color_scheme = Theme.of(context).colorScheme
        items = [self._menu_item(color_scheme, profile) for profile in self.profiles]
        if items:
            items.append(
                PopupMenuItem(
                    value=None,
                    enabled=False,
                    height=1,
                    padding=EdgeInsets.all(0),
                    child=Container(height=1, color=color_scheme.outlineVariant),
                )
            )
        items.append(
            PopupMenuItem(
                value=self._MENU_ITEM_MODEL_MANAGE,
                height=40,
                child=Row(
                    mainAxisSize=MainAxisSize.min,
                    children=[
                        Icon(
                            Icons.settings,
                            size=16,
                            color=color_scheme.onSurfaceVariant,
                        ),
                        SizedBox(width=8),
                        Text(
                            "Manage models\u2026",
                            style=TextStyle(
                                fontSize=13,
                                color=color_scheme.onSurface,
                            ),
                        ),
                    ],
                ),
            )
        )
        return items

    def _shell_menu_item(self, color_scheme, shell):
        is_selected = shell.id in self.selected_shell_ids
        type_label = RockyShellTemplates.label(shell.shell_type)
        target = RockyShellTemplates.target(shell)
        subtitle = f"{type_label} - {target}" if target else type_label
        return PopupMenuItem(
            value=shell.id,
            height=44,
            child=Row(
                mainAxisSize=MainAxisSize.max,
                children=[
                    Icon(
                        Icons.check if is_selected else Icons.circle,
                        size=14,
                        color=(
                            color_scheme.primary if is_selected else Colors.transparent
                        ),
                    ),
                    SizedBox(width=8),
                    Expanded(
                        child=Column(
                            crossAxisAlignment=CrossAxisAlignment.start,
                            children=[
                                Text(
                                    shell.display_name or "Untitled environment",
                                    style=TextStyle(
                                        fontSize=13,
                                        fontWeight=FontWeight.w600,
                                        color=color_scheme.onSurface,
                                    ),
                                ),
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
                ],
            ),
        )

    def _shell_item_builder(self, context):
        color_scheme = Theme.of(context).colorScheme
        items = [self._shell_menu_item(color_scheme, shell) for shell in self.shells]
        if items:
            items.append(
                PopupMenuItem(
                    value=None,
                    enabled=False,
                    height=1,
                    padding=EdgeInsets.all(0),
                    child=Container(height=1, color=color_scheme.outlineVariant),
                )
            )
        items.append(
            PopupMenuItem(
                value=self._MENU_ITEM_SHELL_MANAGE,
                height=40,
                child=Row(
                    mainAxisSize=MainAxisSize.min,
                    children=[
                        Icon(
                            Icons.settings, size=16, color=color_scheme.onSurfaceVariant
                        ),
                        SizedBox(width=8),
                        Text(
                            "Manage environments\u2026",
                            style=TextStyle(fontSize=13, color=color_scheme.onSurface),
                        ),
                    ],
                ),
            )
        )
        return items

    def _menu(
        self,
        *,
        context,
        label,
        item_builder,
        on_selected,
        enabled=True,
        disabled_tooltip=None,
    ):
        color_scheme = Theme.of(context).colorScheme
        foreground = (
            color_scheme.onSurface
            if enabled
            else color_scheme.onSurface.withOpacity(0.4)
        )
        icon_color = (
            color_scheme.onSurfaceVariant
            if enabled
            else color_scheme.onSurfaceVariant.withOpacity(0.45)
        )
        chip = Container(
            padding=EdgeInsets.fromLTRB(10, 6, 8, 6),
            child=Row(
                mainAxisSize=MainAxisSize.min,
                children=[
                    Text(
                        label,
                        style=TextStyle(
                            fontSize=14,
                            fontWeight=FontWeight.w600,
                            color=foreground,
                        ),
                    ),
                    SizedBox(width=4),
                    Icon(Icons.expand_more, size=18, color=icon_color),
                ],
            ),
        )
        menu = PopupMenuButton(
            itemBuilder=item_builder,
            onSelected=on_selected,
            padding=EdgeInsets.all(0),
            tooltip="",
            constraints=BoxConstraints.tightFor(width=self._MENU_WIDTH),
            enabled=enabled,
            child=chip,
        )
        if not enabled and disabled_tooltip:
            return Tooltip(message=disabled_tooltip, child=menu)
        return menu

    def build(self, context):
        model_menu = self._menu(
            context=context,
            label=self._selected_label(),
            item_builder=self._item_builder,
            on_selected=lambda v: self._on_selected(context, v),
        )
        shell_disabled_reason = self._shell_disabled_reason()
        shells_enabled = shell_disabled_reason is None
        shell_menu = self._menu(
            context=context,
            label=self._environment_label(),
            item_builder=self._shell_item_builder,
            on_selected=lambda v: self._on_shell_selected(context, v),
            enabled=shells_enabled,
            disabled_tooltip=shell_disabled_reason,
        )
        return Container(
            padding=EdgeInsets.fromLTRB(8, 8, 8, 8),
            child=Row(children=[model_menu, SizedBox(width=6), shell_menu]),
        )


class _ChatSetupPrompt(StatelessWidget):
    def __init__(self, *, reason, on_open_settings, key=None):
        super().__init__(key=key)
        self.reason = reason
        self.on_open_settings = on_open_settings

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        return Container(
            padding=EdgeInsets.all(20),
            child=Column(
                mainAxisAlignment=MainAxisAlignment.center,
                crossAxisAlignment=CrossAxisAlignment.center,
                children=[
                    Icon(
                        Icons.tune,
                        size=36,
                        color=color_scheme.onSurfaceVariant,
                    ),
                    SizedBox(height=12),
                    Text(
                        self.reason,
                        textAlign=TextAlign.center,
                        style=TextStyle(
                            fontSize=13,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                    SizedBox(height=14),
                    Material(
                        color=color_scheme.primary,
                        borderRadius=BorderRadius.circular(8),
                        child=InkWell(
                            borderRadius=BorderRadius.circular(8),
                            onTap=lambda: self.on_open_settings(),
                            child=Container(
                                padding=EdgeInsets.symmetric(
                                    horizontal=16, vertical=10
                                ),
                                child=Text(
                                    "Open Settings",
                                    style=TextStyle(
                                        fontSize=13,
                                        fontWeight=FontWeight.w600,
                                        color=color_scheme.onPrimary,
                                    ),
                                ),
                            ),
                        ),
                    ),
                ],
            ),
        )


_STATUS_MESSAGES = {
    RockyAgentStatus.INITIALIZING: "Initializing model\u2026",
    RockyAgentStatus.SENDING: "Sending\u2026",
    RockyAgentStatus.THINKING: "Thinking\u2026",
    RockyAgentStatus.RESPONDING: "Responding\u2026",
    RockyAgentStatus.EXECUTING: "Executing tools\u2026",
}


class _ChatStatusBanner(StatefulWidget):
    def __init__(self, *, chat, key=None):
        super().__init__(key=key)
        self.chat = chat

    def createState(self):
        return _ChatStatusBannerState()


class _ChatStatusBannerState(State[_ChatStatusBanner]):
    def initState(self):
        self._chat = None
        self._attach(self.widget.chat)

    def dispose(self):
        self._detach()

    def didUpdateWidget(self, old_widget):
        if old_widget.chat is not self.widget.chat:
            self._detach()
            self._attach(self.widget.chat)

    def _attach(self, chat):
        self._chat = chat
        if chat is not None:
            chat.addListener(self._on_chat_changed)

    def _detach(self):
        if self._chat is not None:
            self._chat.removeListener(self._on_chat_changed)
            self._chat = None

    def _on_chat_changed(self):
        self.setState(lambda: None)

    def build(self, context):
        chat = self._chat
        message = _STATUS_MESSAGES.get(chat.status) if chat is not None else None
        if message is None:
            return SizedBox(width=0, height=0)
        color_scheme = Theme.of(context).colorScheme
        return Container(
            margin=EdgeInsets.fromLTRB(16, 0, 16, 8),
            padding=EdgeInsets.symmetric(horizontal=12, vertical=8),
            decoration=BoxDecoration(
                color=color_scheme.secondaryContainer,
                borderRadius=BorderRadius.circular(10),
                border=Border.all(width=0.5, color=color_scheme.outlineVariant),
            ),
            child=Row(
                mainAxisSize=MainAxisSize.min,
                crossAxisAlignment=CrossAxisAlignment.center,
                children=[
                    Container(
                        width=14,
                        height=14,
                        child=CircularProgressIndicator(
                            strokeWidth=2.0,
                            color=color_scheme.primary,
                        ),
                    ),
                    SizedBox(width=10),
                    Expanded(
                        child=Text(
                            message,
                            style=TextStyle(
                                fontSize=12,
                                color=color_scheme.onSecondaryContainer,
                            ),
                        ),
                    ),
                ],
            ),
        )


class RockyChatPage(StatelessWidget):
    def __init__(
        self,
        *,
        profiles,
        selected_profile_id,
        on_select_profile,
        shells,
        selected_shell_ids,
        on_set_shell_selected,
        needs_setup,
        setup_reason,
        settings_ready,
        chat,
        on_send_message,
        on_open_model_manager,
        on_open_shell_manager,
        key=None,
    ):
        super().__init__(key=key)
        self.profiles = profiles
        self.selected_profile_id = selected_profile_id
        self.on_select_profile = on_select_profile
        self.shells = shells or []
        self.selected_shell_ids = selected_shell_ids or []
        self.on_set_shell_selected = on_set_shell_selected
        self.needs_setup = needs_setup
        self.setup_reason = setup_reason
        self.settings_ready = settings_ready
        self.chat = chat
        self.on_send_message = on_send_message
        self.on_open_model_manager = on_open_model_manager
        self.on_open_shell_manager = on_open_shell_manager

    def _body(self):
        if self.needs_setup:
            return _ChatSetupPrompt(
                reason=self.setup_reason or "Configure a model to begin.",
                on_open_settings=self.on_open_model_manager,
            )

        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=[
                Expanded(child=RockyChatMessageList(chat=self.chat)),
                _ChatStatusBanner(chat=self.chat),
            ],
        )

    def build(self, context):
        return Expanded(
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=[
                    RockyChatHeader(
                        profiles=self.profiles,
                        selected_profile_id=self.selected_profile_id,
                        on_select_profile=self.on_select_profile,
                        shells=self.shells,
                        selected_shell_ids=self.selected_shell_ids,
                        on_set_shell_selected=self.on_set_shell_selected,
                        on_open_model_manager=self.on_open_model_manager,
                        on_open_shell_manager=self.on_open_shell_manager,
                    ),
                    Expanded(child=self._body()),
                    RockyChatComposer(
                        chat=self.chat,
                        settings_ready=self.settings_ready,
                        on_send=self.on_send_message,
                    ),
                ],
            ),
        )
