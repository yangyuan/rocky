from typing import Callable

from flut.flutter.widgets import State, StatefulWidget

from rocky.chats import RockyChats
from rocky.settings import RockySettings
from rocky.widgets.chat.page import RockyChatPage


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
        self._current = self.widget.chats.current
        self.widget.chats.addListener(self._on_chats_changed)
        self.widget.settings.addListener(self._on_settings_changed)

    def dispose(self):
        self.widget.chats.removeListener(self._on_chats_changed)
        self.widget.settings.removeListener(self._on_settings_changed)

    def _on_chats_changed(self):
        new_current = self.widget.chats.current
        if new_current is self._current:
            return
        self._current = new_current
        self.setState(lambda: None)

    def _on_settings_changed(self):
        self.setState(lambda: None)

    def build(self, context):
        settings = self.widget.settings
        current = self._current
        settings_ready, settings_reason = settings.chat_ready()
        return RockyChatPage(
            profiles=settings.profiles,
            selected_profile_id=settings.selected_profile_id,
            on_select_profile=settings.select_profile,
            shells=settings.shells,
            selected_shell_ids=settings.selected_shell_ids,
            on_set_shell_selected=settings.set_shell_selected,
            needs_setup=not settings_ready,
            setup_reason=settings_reason,
            settings_ready=settings_ready,
            chat=current,
            on_send_message=current.send_message,
            on_open_model_manager=lambda: self.widget.on_open_settings("models"),
            on_open_shell_manager=lambda: self.widget.on_open_settings("shells"),
        )
