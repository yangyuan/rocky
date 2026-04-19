from __future__ import annotations

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
from flut.flutter.widgets import (
    Column,
    Container,
    Row,
    SizedBox,
    State,
    StatefulWidget,
    StatelessWidget,
    Text,
)
from flut.flutter.widgets.navigator import Navigator

from rocky.chats import RockyChats
from rocky.settings import RockySettings
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.field import RockySettingsField


class RockySettingsChatsPage(StatefulWidget):
    def __init__(self, *, settings: RockySettings, chats: RockyChats, key=None):
        super().__init__(key=key)
        self.settings = settings
        self.chats = chats

    def createState(self):
        return _RockySettingsChatsPageState()


class _RockySettingsChatsPageState(State[RockySettingsChatsPage]):
    def initState(self):
        max_chats = self.widget.settings.chats.max_chats
        self._draft_max_chats = "" if max_chats is None else str(max_chats)
        self._error: str | None = None

    def _on_max_chats_changed(self, raw: str) -> None:
        new_value = (raw or "").strip()
        had_error = self._error is not None

        def _apply():
            self._draft_max_chats = new_value
            self._error = None

        if had_error:
            self.setState(_apply)
        else:
            self._draft_max_chats = new_value
            self.setState(lambda: None)

    def _parse_max_chats(self) -> tuple[bool, int | None]:
        text = self._draft_max_chats.strip()
        if not text:
            return True, None
        try:
            value = int(text)
        except ValueError:
            return False, None
        if value <= 0:
            return False, None
        return True, value

    def _is_dirty(self) -> bool:
        ok, value = self._parse_max_chats()
        if not ok:
            return False
        return value != self.widget.settings.chats.max_chats

    def _save(self):
        ok, value = self._parse_max_chats()
        if not ok:

            def _apply():
                self._error = "Enter a whole number greater than 0, or leave empty."

            self.setState(_apply)
            return
        saved_count = len(self.widget.chats.saved)
        if value is not None and value < saved_count:
            self._confirm_then_commit(value)
            return
        self._commit(value)

    def _commit(self, value):
        self.widget.settings.set_max_chats(value)
        self.setState(lambda: None)

    def _confirm_then_commit(self, value):
        showDialog(
            context=self.context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=_ConfirmDeleteDialog(
                    message="Some chats may be permanently deleted.",
                    on_cancel=lambda: Navigator.pop(dialog_context),
                    on_confirm=lambda: (
                        Navigator.pop(dialog_context),
                        self._commit(value),
                    ),
                ),
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        helper = "Whole number greater than 0. Empty means unlimited."
        if self._error is not None:
            helper = self._error
        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=[
                Text(
                    "Chats",
                    style=TextStyle(
                        fontSize=18,
                        fontWeight=FontWeight.w600,
                        color=color_scheme.onSurface,
                    ),
                ),
                SizedBox(height=4),
                Text(
                    "Set how many chats Rocky keeps. Once you go over the "
                    "limit, the chats you haven't opened in the longest time "
                    "are deleted first.",
                    style=TextStyle(fontSize=12, color=color_scheme.onSurfaceVariant),
                ),
                SizedBox(height=16),
                RockySettingsField(
                    label="Maximum saved chats",
                    value=self._draft_max_chats,
                    on_changed=self._on_max_chats_changed,
                    hint_text="Leave empty for unlimited",
                    helper=helper,
                ),
                SizedBox(height=16),
                Row(
                    mainAxisAlignment=MainAxisAlignment.end,
                    children=[self._save_button(color_scheme)],
                ),
            ],
        )

    def _save_button(self, color_scheme):
        enabled = self._is_dirty()
        if enabled:
            background = color_scheme.primaryContainer
            foreground = color_scheme.onPrimaryContainer
        else:
            background = color_scheme.surfaceContainerHighest
            foreground = color_scheme.onSurfaceVariant
        radius = BorderRadius.circular(8)
        content = Container(
            padding=EdgeInsets.symmetric(horizontal=14, vertical=7),
            child=Row(
                mainAxisSize=MainAxisSize.min,
                children=[
                    Text(
                        "Save",
                        style=TextStyle(
                            fontSize=13,
                            fontWeight=FontWeight.w500,
                            color=foreground,
                        ),
                    ),
                ],
            ),
        )
        if not enabled:
            return Material(color=background, borderRadius=radius, child=content)
        return Material(
            color=background,
            borderRadius=radius,
            child=InkWell(
                onTap=self._save,
                borderRadius=radius,
                hoverColor=color_scheme.onPrimaryContainer.withOpacity(0.06),
                child=content,
            ),
        )


class _ConfirmDeleteDialog(StatelessWidget):
    def __init__(self, *, message, on_cancel, on_confirm, key=None):
        super().__init__(key=key)
        self.message = message
        self.on_cancel = on_cancel
        self.on_confirm = on_confirm

    def _action_button(self, *, label, on_tap, background, foreground):
        radius = BorderRadius.circular(8)
        return Material(
            color=background,
            borderRadius=radius,
            child=InkWell(
                onTap=on_tap,
                borderRadius=radius,
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=16, vertical=8),
                    child=Text(
                        label,
                        style=TextStyle(
                            fontSize=13,
                            fontWeight=FontWeight.w600,
                            color=foreground,
                        ),
                    ),
                ),
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        body = Container(
            width=380,
            padding=EdgeInsets.all(20),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.start,
                children=[
                    Text(
                        self.message,
                        style=TextStyle(fontSize=13, color=color_scheme.onSurface),
                    ),
                    SizedBox(height=20),
                    Row(
                        mainAxisAlignment=MainAxisAlignment.end,
                        children=[
                            self._action_button(
                                label="Cancel",
                                on_tap=self.on_cancel,
                                background=Colors.transparent,
                                foreground=color_scheme.onSurfaceVariant,
                            ),
                            SizedBox(width=8),
                            self._action_button(
                                label="Save",
                                on_tap=self.on_confirm,
                                background=color_scheme.error,
                                foreground=color_scheme.onError,
                            ),
                        ],
                    ),
                ],
            ),
        )
        return RockyDialog(
            title="Save changes?",
            leading_icon=Icons.delete_outline,
            mode="fit_content",
            on_close=self.on_cancel,
            body=body,
        )
