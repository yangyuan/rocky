from flut.dart.ui import FontWeight
from flut.flutter.foundation.key import ValueKey
from flut.flutter.material import (
    Colors,
    Dialog,
    Icons,
    InkWell,
    Material,
    TextField,
    Theme,
    Tooltip,
    showDialog,
)
from flut.flutter.material.input_border import InputBorder
from flut.flutter.material.input_decorator import InputDecoration
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BorderSide,
    BoxDecoration,
    BoxShape,
    EdgeInsets,
    TextOverflow,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment
from flut.flutter.scheduler import SchedulerBinding
from flut.flutter.services.keyboard_key import LogicalKeyboardKey
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Icon,
    ListView,
    MouseRegion,
    Navigator,
    Row,
    SizedBox,
    State,
    StatefulWidget,
    StatelessWidget,
    Text,
    TextEditingController,
)
from flut.flutter.widgets.focus_manager import FocusNode
from flut.flutter.widgets.shortcuts import CallbackShortcuts, SingleActivator

from rocky.chats import RockyChats
from rocky.widgets.dialog import RockyDialog

EXPANDED_WIDTH = 240
COLLAPSED_WIDTH = 56


class _SidebarItem(StatelessWidget):
    def __init__(
        self,
        *,
        icon,
        label,
        collapsed,
        onTap,
        active=False,
        key=None,
    ):
        super().__init__(key=key)
        self.icon = icon
        self.label = label
        self.collapsed = collapsed
        self.onTap = onTap
        self.active = active

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        text_color = (
            color_scheme.onSecondaryContainer if self.active else color_scheme.onSurface
        )
        background = (
            color_scheme.secondaryContainer if self.active else Colors.transparent
        )

        row_children = []
        if self.icon is not None:
            row_children.append(Icon(self.icon, size=18, color=text_color))
            if not self.collapsed:
                row_children.append(SizedBox(width=10))
        if not self.collapsed:
            row_children.append(
                Expanded(
                    child=Text(
                        self.label,
                        maxLines=1,
                        overflow=TextOverflow.ellipsis,
                        style=TextStyle(
                            fontSize=13,
                            fontWeight=FontWeight.w600,
                            color=text_color,
                        ),
                    ),
                )
            )

        radius = BorderRadius.circular(6)
        tappable = Material(
            color=background,
            borderRadius=radius,
            child=InkWell(
                onTap=self.onTap,
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.08),
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=10, vertical=8),
                    child=Row(
                        mainAxisAlignment=(
                            MainAxisAlignment.center
                            if self.collapsed
                            else MainAxisAlignment.start
                        ),
                        children=row_children,
                    ),
                ),
            ),
        )
        if self.collapsed:
            return Tooltip(message=self.label, child=tappable)
        return tappable


class _DeleteChatConfirmDialog(StatelessWidget):
    def __init__(self, *, title, on_cancel, on_confirm, key=None):
        super().__init__(key=key)
        self.title = title
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
                        f'"{self.title}" will be permanently removed.',
                        style=TextStyle(
                            fontSize=13,
                            color=color_scheme.onSurface,
                        ),
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
                                label="Delete",
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
            title="Delete chat?",
            leading_icon=Icons.delete_outline,
            mode="fit_content",
            on_close=self.on_cancel,
            body=body,
        )


class _ChatRow(StatefulWidget):
    def __init__(self, *, chat, active, on_select, on_delete, on_rename, key=None):
        super().__init__(key=key)
        self.chat = chat
        self.active = active
        self.on_select = on_select
        self.on_delete = on_delete
        self.on_rename = on_rename

    def createState(self):
        return _ChatRowState()


class _ChatRowState(State[_ChatRow]):
    def initState(self):
        self.hovered = False
        self.trash_hovered = False
        self.editing = False
        self._controller = TextEditingController(text="")
        self._focus = FocusNode()
        self._focus.addListener(self._on_focus_change)

    def dispose(self):
        self._focus.removeListener(self._on_focus_change)

    def _on_focus_change(self):
        if self.editing and not self._focus.hasFocus:
            self._cancel_edit()

    def didUpdateWidget(self, old_widget):
        if not self.widget.active and self.editing:
            self.editing = False

    def _set_hover(self, value):
        if self.hovered == value:
            return

        def _apply():
            self.hovered = value
            if not value:
                self.trash_hovered = False

        self.setState(_apply)

    def _set_trash_hover(self, value):
        if self.trash_hovered == value:
            return

        def _apply():
            self.trash_hovered = value

        self.setState(_apply)

    def _on_tap(self):
        if self.widget.active:
            self._begin_edit()
        else:
            self.widget.on_select()

    def _begin_edit(self):
        if self.editing:
            return
        title = self.widget.chat.title or ""
        self._controller.text = title

        def _apply():
            self.editing = True

        self.setState(_apply)
        SchedulerBinding.instance.addPostFrameCallback(
            lambda _: self._focus.requestFocus()
        )

    def _cancel_edit(self):
        if not self.editing:
            return

        def _apply():
            self.editing = False

        self.setState(_apply)
        self._focus.unfocus()

    def _commit_edit(self, value=None):
        if not self.editing:
            return
        text = (value if value is not None else self._controller.text) or ""
        text = text.strip()
        if text and text != (self.widget.chat.title or ""):
            self.widget.on_rename(text)

        def _apply():
            self.editing = False

        self.setState(_apply)
        self._focus.unfocus()

    def _build_editor(self, color_scheme, text_color):
        return CallbackShortcuts(
            bindings={
                SingleActivator(LogicalKeyboardKey.enter): self._commit_edit,
                SingleActivator(LogicalKeyboardKey.escape): self._cancel_edit,
            },
            child=TextField(
                controller=self._controller,
                focusNode=self._focus,
                autofocus=True,
                maxLines=1,
                style=TextStyle(
                    fontSize=13,
                    fontWeight=FontWeight.w600,
                    color=text_color,
                ),
                cursorColor=text_color,
                decoration=InputDecoration(
                    border=InputBorder.none,
                    enabledBorder=InputBorder.none,
                    focusedBorder=InputBorder.none,
                    isDense=True,
                    contentPadding=EdgeInsets.symmetric(horizontal=0, vertical=0),
                ),
                onSubmitted=self._commit_edit,
            ),
        )

    def _confirm_delete(self, context):
        title = self.widget.chat.title or "Untitled chat"
        on_delete = self.widget.on_delete
        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=_DeleteChatConfirmDialog(
                    title=title,
                    on_cancel=lambda: Navigator.pop(dialog_context),
                    on_confirm=lambda: (
                        Navigator.pop(dialog_context),
                        on_delete(),
                    ),
                ),
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        active = self.widget.active
        text_color = (
            color_scheme.onSecondaryContainer if active else color_scheme.onSurface
        )
        background = color_scheme.secondaryContainer if active else Colors.transparent
        radius = BorderRadius.circular(6)

        label = Expanded(
            child=Container(
                padding=EdgeInsets.fromLTRB(10, 8, 4, 8),
                child=(
                    self._build_editor(color_scheme, text_color)
                    if self.editing
                    else Text(
                        self.widget.chat.title or "Untitled chat",
                        maxLines=1,
                        overflow=TextOverflow.ellipsis,
                        style=TextStyle(
                            fontSize=13,
                            fontWeight=FontWeight.w600,
                            color=text_color,
                        ),
                    )
                ),
            ),
        )

        if self.hovered and not self.editing:
            icon_color = (
                color_scheme.onSurface
                if self.trash_hovered
                else color_scheme.onSurface.withOpacity(0.55)
            )
            trash_icon = Material(
                color=Colors.transparent,
                child=InkWell(
                    onTap=lambda: self._confirm_delete(context),
                    borderRadius=BorderRadius.circular(14),
                    hoverColor=color_scheme.onSurface.withOpacity(0.12),
                    child=Container(
                        width=28,
                        height=28,
                        decoration=BoxDecoration(
                            color=color_scheme.surfaceContainerHighest,
                            shape=BoxShape.circle,
                        ),
                        child=Icon(
                            Icons.delete_outline,
                            size=15,
                            color=icon_color,
                        ),
                    ),
                ),
            )
            trailing = Container(
                padding=EdgeInsets.only(right=6),
                child=MouseRegion(
                    onEnter=lambda _e: self._set_trash_hover(True),
                    onExit=lambda _e: self._set_trash_hover(False),
                    child=trash_icon,
                ),
            )
        else:
            trailing = SizedBox(width=0, height=28)

        row = Row(
            children=[label, trailing],
        )

        tappable = Material(
            color=background,
            borderRadius=radius,
            child=InkWell(
                onTap=self._on_tap,
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.08),
                child=row,
            ),
        )

        return MouseRegion(
            onEnter=lambda _e: self._set_hover(True),
            onExit=lambda _e: self._set_hover(False),
            child=tappable,
        )


class RockySidebar(StatefulWidget):
    def __init__(self, *, chats: RockyChats, on_open_settings, key=None):
        super().__init__(key=key)
        self.chats = chats
        self.on_open_settings = on_open_settings

    def createState(self):
        return _RockySidebarState()


class _RockySidebarState(State[RockySidebar]):
    def initState(self):
        self.collapsed = False
        self.widget.chats.addListener(self._on_chats_changed)

    def dispose(self):
        self.widget.chats.removeListener(self._on_chats_changed)

    def _on_chats_changed(self):
        self.setState(lambda: None)

    def _toggle(self):
        def _apply():
            self.collapsed = not self.collapsed

        self.setState(_apply)

    def _header(self, theme):
        color_scheme = theme.colorScheme
        collapsed = self.collapsed
        toggle_icon = Icons.chevron_right if collapsed else Icons.chevron_left
        toggle_button = Tooltip(
            message="Expand sidebar" if collapsed else "Collapse sidebar",
            child=Material(
                color=Colors.transparent,
                child=InkWell(
                    onTap=self._toggle,
                    borderRadius=BorderRadius.circular(6),
                    hoverColor=color_scheme.onSurface.withOpacity(0.08),
                    child=Container(
                        padding=EdgeInsets.all(6),
                        child=Icon(
                            toggle_icon, size=18, color=color_scheme.onSurfaceVariant
                        ),
                    ),
                ),
            ),
        )

        if collapsed:
            children = [toggle_button]
            alignment = MainAxisAlignment.center
        else:
            children = [
                Text(
                    "Rocky",
                    style=TextStyle(
                        fontSize=15,
                        fontWeight=FontWeight.bold,
                        color=color_scheme.onSurface,
                    ),
                ),
                toggle_button,
            ]
            alignment = MainAxisAlignment.spaceBetween

        return Container(
            padding=EdgeInsets.fromLTRB(10, 10, 10, 6),
            child=Row(mainAxisAlignment=alignment, children=children),
        )

    def _chat_list(self, theme):
        chats = self.widget.chats
        current = chats.current
        current_id = current.id if current is not None else None
        saved = chats.saved
        color_scheme = theme.colorScheme

        if self.collapsed:
            return Container()

        if not saved:
            return Container(
                padding=EdgeInsets.fromLTRB(14, 6, 14, 6),
                child=Text(
                    "No saved chats yet",
                    style=TextStyle(
                        fontSize=11,
                        color=color_scheme.onSurfaceVariant,
                    ),
                ),
            )

        header = Container(
            padding=EdgeInsets.fromLTRB(14, 10, 14, 4),
            child=Text(
                "Chats",
                style=TextStyle(
                    fontSize=11,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
        )

        def _row(chat):
            return Container(
                padding=EdgeInsets.symmetric(horizontal=8, vertical=2),
                child=_ChatRow(
                    chat=chat,
                    active=chat.id == current_id,
                    on_select=(lambda cid=chat.id: self.widget.chats.select(cid)),
                    on_delete=(lambda cid=chat.id: self.widget.chats.delete(cid)),
                    on_rename=(lambda title, c=chat: c.set_title(title)),
                    key=ValueKey(f"chat_{chat.id}"),
                ),
            )

        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=[
                header,
                Expanded(
                    child=ListView(
                        padding=EdgeInsets.only(bottom=8),
                        children=[_row(c) for c in saved],
                    ),
                ),
            ],
        )

    def build(self, context):
        theme = Theme.of(context)
        collapsed = self.collapsed
        chats = self.widget.chats

        new_chat_section = Container(
            padding=EdgeInsets.symmetric(horizontal=8, vertical=8),
            child=_SidebarItem(
                icon=Icons.add,
                label="New chat",
                collapsed=collapsed,
                onTap=chats.new_chat,
            ),
        )

        bottom_items = Container(
            padding=EdgeInsets.symmetric(horizontal=8, vertical=8),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=[
                    _SidebarItem(
                        icon=Icons.settings,
                        label="Settings",
                        collapsed=collapsed,
                        onTap=lambda: self.widget.on_open_settings(),
                    ),
                ],
            ),
        )

        color_scheme = theme.colorScheme
        return Container(
            width=COLLAPSED_WIDTH if collapsed else EXPANDED_WIDTH,
            decoration=BoxDecoration(
                border=Border(
                    right=BorderSide(width=1, color=color_scheme.outlineVariant)
                ),
            ),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=[
                    self._header(theme),
                    new_chat_section,
                    Expanded(child=self._chat_list(theme)),
                    bottom_items,
                ],
            ),
        )
