from typing import Callable

from flut.flutter.material import Colors, Dialog, Scaffold, showDialog
from flut.flutter.painting import EdgeInsets
from flut.flutter.widgets import Column, Expanded, Row, StatelessWidget

from rocky.chats import RockyChats
from rocky.settings import RockySettings
from rocky.widgets.app.about import RockyAboutDialog
from rocky.widgets.app.menu import RockyAppMenu
from rocky.widgets.app.sidebar import RockySidebar
from rocky.widgets.chat.host import RockyChatHost
from rocky.widgets.settings.dialog import RockySettingsDialog


class RockyHome(StatelessWidget):
    def __init__(
        self,
        *,
        settings: RockySettings,
        chats: RockyChats,
        on_exit: Callable[[], None],
        key=None,
    ):
        super().__init__(key=key)
        self.settings = settings
        self.chats = chats
        self.on_exit = on_exit

    def _open_settings(self, context):
        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(18),
                child=RockySettingsDialog(
                    settings=self.settings,
                    chats=self.chats,
                ),
            ),
        )

    def _open_about(self, context):
        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=RockyAboutDialog(),
            ),
        )

    def build(self, context):
        open_settings = lambda: self._open_settings(context)
        open_about = lambda: self._open_about(context)

        menu = RockyAppMenu(
            settings=self.settings,
            on_new_chat=self.chats.new_chat,
            on_open_settings=open_settings,
            on_open_about=open_about,
            on_exit=self.on_exit,
        )

        body = Row(
            children=[
                RockySidebar(
                    chats=self.chats,
                    on_open_settings=open_settings,
                ),
                RockyChatHost(
                    settings=self.settings,
                    chats=self.chats,
                    on_open_settings=open_settings,
                ),
            ],
        )

        return Scaffold(body=Column(children=[menu, Expanded(child=body)]))
