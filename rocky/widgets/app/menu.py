from pathlib import Path
from typing import Callable

from flut.dart.ui import Size
from flut.flutter.material import (
    ButtonStyle,
    MenuBar,
    MenuItemButton,
    SubmenuButton,
)
from flut.flutter.painting import EdgeInsets
from flut.flutter.widgets import (
    Expanded,
    Row,
    StatelessWidget,
    Text,
    WidgetStateProperty,
)

from rocky.settings import RockySettings
from rocky.system import RockySystem
from rocky.widgets.app.theme import RockyTheme

ROCKY_PROJECT_URL = "https://github.com/yangyuan/rocky"


class RockyAppMenu(StatelessWidget):
    def __init__(
        self,
        *,
        settings: RockySettings,
        on_new_chat: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_open_about: Callable[[], None],
        on_exit: Callable[[], None],
        key=None,
    ):
        super().__init__(key=key)
        self.settings = settings
        self.on_new_chat = on_new_chat
        self.on_open_settings = on_open_settings
        self.on_open_about = on_open_about
        self.on_exit = on_exit

    def _item(self, label, on_pressed, *, checked=None):
        prefix = "" if checked is None else ("\u2713 " if checked else "   ")
        return MenuItemButton(
            style=self._button_style,
            onPressed=on_pressed,
            child=Text(prefix + label),
        )

    def _submenu(self, label, children):
        return SubmenuButton(
            style=self._button_style,
            menuChildren=children,
            child=Text(label),
        )

    def _open_runtime_folder(self):
        runtime_dir = Path(__file__).resolve().parents[3]
        RockySystem.open_folder(runtime_dir)

    def _open_project_home(self):
        RockySystem.open_url(ROCKY_PROJECT_URL)

    def _theme_submenu(self):
        theme = self.settings.theme
        return self._submenu(
            "Theme",
            [
                self._item(
                    opt.label,
                    (lambda tid=opt.id: self.settings.set_theme_color(tid)),
                    checked=(theme.color == opt.id),
                )
                for opt in RockyTheme.options()
            ],
        )

    def build(self, context):
        self._button_style = ButtonStyle(
            padding=WidgetStateProperty.all(
                EdgeInsets.only(left=12, top=12, right=12, bottom=12)
            ),
            minimumSize=WidgetStateProperty.all(Size(64, 24)),
        )
        theme = self.settings.theme

        bar = MenuBar(
            children=[
                self._submenu(
                    "File",
                    [
                        self._item("Settings", self.on_open_settings),
                        self._item("Exit", self.on_exit),
                    ],
                ),
                self._submenu(
                    "Agent",
                    [
                        self._item("New Chat", self.on_new_chat),
                    ],
                ),
                self._submenu(
                    "View",
                    [
                        self._item("Runtime Folder", self._open_runtime_folder),
                    ],
                ),
                self._submenu(
                    "Window",
                    [
                        self._item(
                            "Dark Mode",
                            self.settings.toggle_dark_mode,
                            checked=theme.brightness == "dark",
                        ),
                        self._item(
                            "Tint",
                            self.settings.toggle_tint,
                            checked=theme.tint,
                        ),
                        self._theme_submenu(),
                    ],
                ),
                self._submenu(
                    "Help",
                    [
                        self._item("Project Home", self._open_project_home),
                        self._item("About", self.on_open_about),
                    ],
                ),
            ],
        )
        return Row(children=[Expanded(child=bar)])
