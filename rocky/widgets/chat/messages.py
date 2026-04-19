from flut.dart.ui import FontWeight
from flut.flutter.foundation.key import ValueKey
from flut.flutter.material import (
    Colors,
    Icons,
    InkWell,
    Material,
    SelectableText,
    Theme,
)
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment
from flut.flutter.scheduler import SchedulerBinding
from flut.flutter.widgets import (
    Column,
    Container,
    Flexible,
    Icon,
    ListView,
    Row,
    ScrollController,
    SizedBox,
    State,
    StatefulWidget,
    StatelessWidget,
    Text,
)

from rocky.widgets.chat.attachments import RockyAttachmentBubbleStrip
from rocky.widgets.rendering.markdown import RockyMarkdown

CHAT_FONT_SIZE = 14
METADATA_FONT_SIZE = 12


class _BubbleUpgradeQueue:
    _pending: list = []
    _drains: list = []
    _scheduled: bool = False

    @classmethod
    def enqueue(cls, callback) -> None:
        cls._pending.append(callback)
        cls._schedule()

    @classmethod
    def on_drain(cls, callback) -> None:
        if not cls._pending:
            callback()
            return
        cls._drains.append(callback)

    @classmethod
    def _schedule(cls) -> None:
        if cls._scheduled:
            return
        cls._scheduled = True
        SchedulerBinding.instance.addPostFrameCallback(cls._pump)

    @classmethod
    def _pump(cls, _stamp) -> None:
        cls._scheduled = False
        if cls._pending:
            try:
                cls._pending.pop(0)()
            except Exception:
                pass
        if cls._pending:
            cls._schedule()
            return
        drains, cls._drains = cls._drains, []
        for drain in drains:
            try:
                drain()
            except Exception:
                pass


class RockyMarkdownToggleButton(StatelessWidget):
    def __init__(self, *, rendered: bool, on_toggle, key=None):
        super().__init__(key=key)
        self.rendered = rendered
        self.on_toggle = on_toggle

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        icon_data = Icons.code if self.rendered else Icons.article_outlined
        return Material(
            color=Colors.transparent,
            child=InkWell(
                onTap=self.on_toggle,
                borderRadius=BorderRadius.circular(10),
                child=Container(
                    padding=EdgeInsets.all(2),
                    child=Icon(
                        icon_data,
                        size=14,
                        color=color_scheme.onSurfaceVariant,
                    ),
                ),
            ),
        )


class RockyChatBubbleFrame(StatelessWidget):
    USER_LABEL = "You"
    ASSISTANT_LABEL = "Rocky"

    def __init__(self, *, role: str, child, metadata_action=None, key=None):
        super().__init__(key=key)
        self.role = role
        self.child = child
        self.metadata_action = metadata_action

    @classmethod
    def text_color_for(cls, color_scheme, role: str):
        if role == "user":
            return color_scheme.onPrimaryContainer
        return color_scheme.onSurface

    def _resolve_palette(self, color_scheme):
        if self.role == "user":
            return (
                color_scheme.primaryContainer,
                color_scheme.primary.withOpacity(0.5),
            )
        return (
            color_scheme.surfaceContainerLow,
            color_scheme.outlineVariant.withOpacity(0.5),
        )

    def _resolve_label(self) -> str:
        return self.USER_LABEL if self.role == "user" else self.ASSISTANT_LABEL

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        background, border = self._resolve_palette(color_scheme)
        align_user = self.role == "user"
        main_alignment = (
            MainAxisAlignment.end if align_user else MainAxisAlignment.start
        )
        cross_alignment = (
            CrossAxisAlignment.end if align_user else CrossAxisAlignment.start
        )

        bubble = Container(
            padding=EdgeInsets.symmetric(horizontal=14, vertical=8),
            decoration=BoxDecoration(
                color=background,
                borderRadius=BorderRadius.circular(12),
                border=Border.all(width=1, color=border),
            ),
            child=self.child,
        )

        metadata_children = [
            Text(
                self._resolve_label(),
                style=TextStyle(
                    fontSize=METADATA_FONT_SIZE,
                    fontWeight=FontWeight.w600,
                    color=Colors.grey,
                ),
            ),
        ]
        if self.metadata_action is not None:
            metadata_children.append(SizedBox(width=4))
            metadata_children.append(self.metadata_action)

        return Container(
            margin=EdgeInsets.only(bottom=12),
            child=Column(
                crossAxisAlignment=cross_alignment,
                children=[
                    Row(
                        mainAxisAlignment=main_alignment,
                        crossAxisAlignment=CrossAxisAlignment.center,
                        children=metadata_children,
                    ),
                    SizedBox(height=3),
                    Row(
                        mainAxisAlignment=main_alignment,
                        crossAxisAlignment=CrossAxisAlignment.start,
                        children=[Flexible(child=bubble)],
                    ),
                ],
            ),
        )


class RockyChatBubble(StatefulWidget):
    def __init__(self, *, role, content, attachments=(), key=None):
        super().__init__(key=key)
        self.role = role
        self.content = content or ""
        self.attachments = list(attachments or [])

    def createState(self):
        return _RockyChatBubbleState()


class _RockyChatBubbleState(State[RockyChatBubble]):
    def initState(self):
        self._rendered = True
        self._ready = self.widget.role == "user"
        self._disposed = False
        if not self._ready:
            _BubbleUpgradeQueue.enqueue(self._mark_ready)

    def dispose(self):
        self._disposed = True

    def _mark_ready(self):
        if self._disposed or self._ready:
            return

        def _apply():
            self._ready = True

        self.setState(_apply)

    def _toggle(self):
        def _flip():
            self._rendered = not self._rendered

        self.setState(_flip)

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        text_color = RockyChatBubbleFrame.text_color_for(color_scheme, self.widget.role)
        base_style = TextStyle(fontSize=CHAT_FONT_SIZE, color=text_color)
        is_user = self.widget.role == "user"
        show_markdown = not is_user and self._ready and self._rendered

        if is_user:
            text_widget = SelectableText(self.widget.content, style=base_style)
            if self.widget.attachments:
                child = Column(
                    crossAxisAlignment=CrossAxisAlignment.start,
                    children=[
                        RockyAttachmentBubbleStrip(
                            attachments=self.widget.attachments,
                        ),
                        text_widget,
                    ],
                )
            else:
                child = text_widget
            metadata_action = None
        elif show_markdown:
            child = RockyMarkdown(content=self.widget.content, base_style=base_style)
            metadata_action = RockyMarkdownToggleButton(
                rendered=True,
                on_toggle=self._toggle,
            )
        else:
            child = SelectableText(self.widget.content, style=base_style)
            metadata_action = RockyMarkdownToggleButton(
                rendered=self._rendered,
                on_toggle=self._toggle,
            )

        return RockyChatBubbleFrame(
            role=self.widget.role,
            child=child,
            metadata_action=metadata_action,
        )


class _RockyAssistantStreamingBubble(StatefulWidget):
    def __init__(self, *, message, stream_notifier, key=None):
        super().__init__(key=key)
        self.message = message
        self.stream_notifier = stream_notifier

    def createState(self):
        return _RockyAssistantStreamingBubbleState()


class _RockyAssistantStreamingBubbleState(State[_RockyAssistantStreamingBubble]):
    def initState(self):
        self._rendered = True
        self.widget.stream_notifier.addListener(self._on_stream)

    def dispose(self):
        self.widget.stream_notifier.removeListener(self._on_stream)

    def didUpdateWidget(self, old_widget):
        if old_widget.stream_notifier is not self.widget.stream_notifier:
            old_widget.stream_notifier.removeListener(self._on_stream)
            self.widget.stream_notifier.addListener(self._on_stream)

    def _on_stream(self):
        self.setState(lambda: None)

    def _toggle(self):
        def _flip():
            self._rendered = not self._rendered

        self.setState(_flip)

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        text_color = RockyChatBubbleFrame.text_color_for(color_scheme, "assistant")
        base_style = TextStyle(fontSize=CHAT_FONT_SIZE, color=text_color)
        content = self.widget.message.content or ""
        if self._rendered:
            child = RockyMarkdown(
                content=content,
                base_style=base_style,
                trailing_cursor=True,
            )
        else:
            child = SelectableText(content + " \u258d", style=base_style)
        return RockyChatBubbleFrame(
            role="assistant",
            child=child,
            metadata_action=RockyMarkdownToggleButton(
                rendered=self._rendered,
                on_toggle=self._toggle,
            ),
        )


class RockyChatMessageList(StatefulWidget):
    def __init__(self, *, chat, key=None):
        super().__init__(key=key)
        self.chat = chat

    def createState(self):
        return _RockyChatMessageListState()


class _RockyChatMessageListState(State[RockyChatMessageList]):
    def initState(self):
        self._scroll = ScrollController()
        self._last_count = 0
        self._was_streaming = False
        self._chat = None
        self._stream_notifier = None
        self._attach(self.widget.chat)
        self._arm_drain_jump()

    def dispose(self):
        self._detach()

    def didUpdateWidget(self, old_widget):
        if old_widget.chat is not self.widget.chat:
            self._detach()
            self._attach(self.widget.chat)
            self._arm_drain_jump()

    def _attach(self, chat):
        self._chat = chat
        if chat is None:
            return
        chat.addListener(self._on_chat_changed)
        self._stream_notifier = chat.stream_notifier
        self._stream_notifier.addListener(self._on_stream)

    def _detach(self):
        if self._chat is not None:
            self._chat.removeListener(self._on_chat_changed)
            self._chat = None
        if self._stream_notifier is not None:
            self._stream_notifier.removeListener(self._on_stream)
            self._stream_notifier = None

    def _on_chat_changed(self):
        self.setState(lambda: None)

    def _arm_drain_jump(self):
        def _on_register(_stamp):
            _BubbleUpgradeQueue.on_drain(_on_drain)

        def _on_drain():
            SchedulerBinding.instance.addPostFrameCallback(_on_laid_out)

        def _on_laid_out(_stamp):
            self._scroll_to_bottom(force=True)

        SchedulerBinding.instance.addPostFrameCallback(_on_register)

    def _on_stream(self):
        self._scroll_to_bottom()

    def _is_at_bottom(self):
        if not self._scroll.hasClients:
            return True
        try:
            position = self._scroll.position
            return position.pixels >= position.maxScrollExtent - 60
        except Exception:
            return True

    def _scroll_to_bottom(self, force=False):
        if not force and not self._is_at_bottom():
            return

        def _jump(_):
            if not self._scroll.hasClients:
                return
            try:
                self._scroll.jumpTo(self._scroll.position.maxScrollExtent)
            except Exception:
                pass

        SchedulerBinding.instance.addPostFrameCallback(_jump)

    def build(self, context):
        chat = self._chat
        messages = chat.messages if chat is not None else []
        stream_notifier = chat.stream_notifier if chat is not None else None

        force = len(messages) > self._last_count
        self._last_count = len(messages)
        last_streaming = bool(messages) and messages[-1].streaming
        stream_ended = self._was_streaming and not last_streaming
        self._was_streaming = last_streaming
        if messages:
            self._scroll_to_bottom(force=force)
        if force or stream_ended:
            self._arm_drain_jump()

        children = []
        for index, message in enumerate(messages):
            if message.streaming and message.role == "assistant":
                children.append(
                    _RockyAssistantStreamingBubble(
                        message=message,
                        stream_notifier=stream_notifier,
                        key=ValueKey(f"chat_stream_{index}"),
                    )
                )
            else:
                children.append(
                    RockyChatBubble(
                        role=message.role,
                        content=message.content,
                        attachments=list(message.attachments or []),
                        key=ValueKey(f"chat_{index}"),
                    )
                )

        return ListView(
            controller=self._scroll,
            padding=EdgeInsets.fromLTRB(16, 12, 16, 12),
            children=children,
            cacheExtent=50000,
        )
