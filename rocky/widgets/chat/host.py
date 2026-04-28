from typing import Callable

from flut.flutter.widgets import State, StatefulWidget

from rocky.chats import RockyChats
from rocky.settings import RockySettings
from rocky.widgets.chat.page import RockyChatPage
from rocky.widgets.explorer.shell import RockyShellExplorerDialog


class RockyChatHost(StatefulWidget):
    def __init__(
        self,
        *,
        settings: RockySettings,
        chats: RockyChats,
        on_open_settings: Callable[[], None],
        key=None,
    ):
        super().__init__(key=key)
        self.settings = settings
        self.chats = chats
        self.on_open_settings = on_open_settings

    def createState(self):
        return _RockyChatHostState()


class _RockyChatHostState(State[RockyChatHost]):
    def initState(self):
        self.widget.chats.addListener(self._on_changed)
        self.widget.settings.addListener(self._on_changed)

    def dispose(self):
        self.widget.chats.removeListener(self._on_changed)
        self.widget.settings.removeListener(self._on_changed)

    def _on_changed(self):
        self.setState(lambda: None)

    def build(self, context):
        settings = self.widget.settings
        chats = self.widget.chats
        current = chats.current
        chat_ready, chat_reason = chats.chat_ready(current)
        return RockyChatPage(
            model_profiles=settings.model_profiles,
            selected_model_profile_id=chats.model_profile_id_for(current),
            on_select_model_profile=current.set_selected_model_profile,
            shell_profiles=settings.shell_profiles,
            selected_shell_profile_ids=chats.shell_profile_ids_for(current),
            on_set_shell_profile_selected=lambda shell_profile_id, selected: chats.toggle_shell_profile(
                current, shell_profile_id, selected
            ),
            needs_setup=not chat_ready,
            setup_reason=chat_reason,
            settings_ready=chat_ready,
            chat=current,
            on_send_message=current.send_message,
            on_open_model_manager=lambda: self.widget.on_open_settings("models"),
            on_open_shell_manager=lambda: self.widget.on_open_settings("shells"),
            on_open_shell_explorer=lambda shell_profile_id: RockyShellExplorerDialog.open_shell(
                self.context,
                settings.shell_profiles,
                shell_profile_id,
            ),
        )
