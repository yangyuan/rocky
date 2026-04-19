from flut.flutter.material import Icons, IconButton, TextField, Theme
from flut.flutter.material.input_border import InputBorder
from flut.flutter.material.input_decorator import InputDecoration
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BorderSide,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment
from flut.flutter.scheduler import SchedulerBinding
from flut.flutter.services.keyboard_key import LogicalKeyboardKey
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Icon,
    Row,
    SizedBox,
    State,
    StatefulWidget,
    TextEditingController,
)
from flut.flutter.widgets.focus_manager import FocusNode
from flut.flutter.widgets.shortcuts import CallbackShortcuts, SingleActivator

from rocky.widgets.chat.attachments import (
    RockyAttachmentComposerStrip,
    RockyAttachmentPicker,
)
from rocky.widgets.chat.messages import CHAT_FONT_SIZE


class RockyChatComposer(StatefulWidget):
    def __init__(
        self,
        *,
        chat,
        settings_ready,
        on_send,
        key=None,
    ):
        super().__init__(key=key)
        self.chat = chat
        self.settings_ready = settings_ready
        self.on_send = on_send

    def createState(self):
        return _RockyChatComposerState()


class _RockyChatComposerState(State[RockyChatComposer]):
    def initState(self):
        self._controller = TextEditingController(text="")
        self._focus = FocusNode()
        self._chat = None
        self._attachments = []
        self._attach(self.widget.chat)

    def dispose(self):
        self._detach()

    def didUpdateWidget(self, old_widget):
        if old_widget.chat is not self.widget.chat:
            self._detach()
            self._attachments = []
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

    def _on_attach(self):
        picked = RockyAttachmentPicker.pick()
        if not picked:
            return

        def _apply():
            self._attachments = list(self._attachments) + picked

        self.setState(_apply)

    def _remove_attachment(self, index):
        if index < 0 or index >= len(self._attachments):
            return

        def _apply():
            del self._attachments[index]

        self.setState(_apply)

    def _submit(self, value=None):
        widget = self.widget
        chat = self._chat
        enabled = widget.settings_ready and chat is not None and chat.can_send
        busy = chat is not None and chat.busy
        if not enabled or busy:
            return
        text = (value if value is not None else self._controller.text) or ""
        text = text.strip()
        attachments = list(self._attachments)
        if not text and not attachments:
            return
        self._controller.clear()
        self._attachments = []
        widget.on_send(text, attachments)
        SchedulerBinding.instance.addPostFrameCallback(
            lambda _: self._focus.requestFocus()
        )

    def _build_attach_button(self, color_scheme, enabled):
        icon_color = (
            color_scheme.onSurfaceVariant
            if enabled
            else color_scheme.onSurface.withOpacity(0.3)
        )
        return IconButton(
            onPressed=(self._on_attach if enabled else None),
            icon=Container(
                width=28,
                height=28,
                decoration=BoxDecoration(
                    color=color_scheme.surfaceContainerHighest,
                    borderRadius=BorderRadius.circular(14),
                ),
                child=Icon(Icons.add, size=18, color=icon_color),
            ),
            padding=EdgeInsets.all(2),
        )

    def build(self, context):
        widget = self.widget
        chat = self._chat
        enabled = widget.settings_ready and chat is not None and chat.can_send
        busy = chat is not None and chat.busy
        color_scheme = Theme.of(context).colorScheme
        children = []

        children.append(
            RockyAttachmentComposerStrip(
                attachments=self._attachments,
                on_remove=self._remove_attachment,
            )
        )

        send_enabled = enabled and not busy
        send_background = (
            color_scheme.primary
            if send_enabled
            else color_scheme.surfaceContainerHighest
        )
        send_foreground = (
            color_scheme.onPrimary if send_enabled else color_scheme.onSurfaceVariant
        )

        children.append(
            Container(
                padding=EdgeInsets.fromLTRB(4, 4, 4, 4),
                decoration=BoxDecoration(
                    color=color_scheme.surfaceContainerLowest,
                    borderRadius=BorderRadius.circular(24),
                    border=Border.all(width=1, color=color_scheme.outlineVariant),
                ),
                child=Row(
                    crossAxisAlignment=CrossAxisAlignment.center,
                    children=[
                        self._build_attach_button(color_scheme, enabled and not busy),
                        Expanded(
                            child=CallbackShortcuts(
                                bindings={
                                    SingleActivator(
                                        LogicalKeyboardKey.enter
                                    ): self._submit,
                                },
                                child=TextField(
                                    controller=self._controller,
                                    focusNode=self._focus,
                                    enabled=enabled,
                                    maxLines=None,
                                    minLines=1,
                                    style=TextStyle(
                                        fontSize=CHAT_FONT_SIZE,
                                        color=color_scheme.onSurface,
                                    ),
                                    decoration=InputDecoration(
                                        border=InputBorder.none,
                                        enabledBorder=InputBorder.none,
                                        focusedBorder=InputBorder.none,
                                        disabledBorder=InputBorder.none,
                                        isDense=True,
                                        contentPadding=EdgeInsets.symmetric(
                                            horizontal=4, vertical=8
                                        ),
                                        hintStyle=TextStyle(
                                            fontSize=CHAT_FONT_SIZE,
                                            color=color_scheme.onSurfaceVariant,
                                        ),
                                        hintText=(
                                            "Streaming..."
                                            if busy
                                            else (
                                                "Message Rocky"
                                                if enabled
                                                else "Configure a model to start chatting"
                                            )
                                        ),
                                    ),
                                ),
                            ),
                        ),
                        SizedBox(width=6),
                        IconButton(
                            onPressed=(
                                (lambda: self._submit()) if send_enabled else None
                            ),
                            icon=Container(
                                width=28,
                                height=28,
                                decoration=BoxDecoration(
                                    color=send_background,
                                    borderRadius=BorderRadius.circular(14),
                                ),
                                child=Icon(
                                    Icons.arrow_upward,
                                    color=send_foreground,
                                    size=18,
                                ),
                            ),
                            padding=EdgeInsets.all(2),
                        ),
                    ],
                ),
            ),
        )

        return Container(
            padding=EdgeInsets.fromLTRB(16, 10, 16, 12),
            decoration=BoxDecoration(
                color=color_scheme.surface,
                border=Border(
                    top=BorderSide(width=1, color=color_scheme.outlineVariant),
                ),
            ),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=children,
            ),
        )
