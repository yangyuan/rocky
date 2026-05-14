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
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment
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
from flut.flutter.widgets.navigator import Navigator

from rocky.chats import RockyChats
from rocky.widgets.dialog import RockyDialog


class RockySettingsTemplatesPage(StatefulWidget):
    def __init__(self, *, chats: RockyChats, key=None):
        super().__init__(key=key)
        self.chats = chats

    def createState(self):
        return _RockySettingsTemplatesPageState()


class _RockySettingsTemplatesPageState(State[RockySettingsTemplatesPage]):
    def initState(self):
        self.widget.chats.addListener(self._on_chats_changed)

    def dispose(self):
        self.widget.chats.removeListener(self._on_chats_changed)

    def _on_chats_changed(self):
        self.setState(lambda: None)

    def _confirm_delete(self, template_id: str):
        template = next(
            (
                candidate
                for candidate in self.widget.chats.templates
                if candidate.id == template_id
            ),
            None,
        )
        if template is None:
            return
        showDialog(
            context=self.context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=_DeleteTemplateConfirmDialog(
                    label=template.title or "this template",
                    on_cancel=lambda: Navigator.pop(dialog_context),
                    on_confirm=lambda: (
                        Navigator.pop(dialog_context),
                        self.widget.chats.delete_template(template_id),
                    ),
                ),
            ),
        )

    def _template_row(self, color_scheme, template):
        message_count = len(template.data.messages)
        input_label = "Input" if template.data.input_text.strip() else "No input"
        attachment_count = len(template.data.input_attachments)
        attachment_label = f"{attachment_count} attachments"
        summary = f"{message_count} messages - {input_label} - {attachment_label}"
        radius = BorderRadius.circular(8)
        return Container(
            margin=EdgeInsets.only(bottom=8),
            padding=EdgeInsets.fromLTRB(12, 10, 8, 10),
            decoration=BoxDecoration(
                color=color_scheme.surfaceContainerLowest,
                borderRadius=radius,
                border=Border.all(width=1, color=color_scheme.outlineVariant),
            ),
            child=Row(
                children=[
                    Icon(
                        Icons.description_outlined,
                        size=18,
                        color=color_scheme.onSurfaceVariant,
                    ),
                    SizedBox(width=10),
                    Expanded(
                        child=Column(
                            crossAxisAlignment=CrossAxisAlignment.start,
                            children=[
                                Text(
                                    template.title or "Untitled template",
                                    maxLines=1,
                                    style=TextStyle(
                                        fontSize=13,
                                        fontWeight=FontWeight.w600,
                                        color=color_scheme.onSurface,
                                    ),
                                ),
                                SizedBox(height=2),
                                Text(
                                    summary,
                                    maxLines=1,
                                    style=TextStyle(
                                        fontSize=11,
                                        color=color_scheme.onSurfaceVariant,
                                    ),
                                ),
                            ],
                        ),
                    ),
                    Material(
                        color=Colors.transparent,
                        borderRadius=BorderRadius.circular(16),
                        child=InkWell(
                            onTap=lambda template_id=template.id: self._confirm_delete(
                                template_id
                            ),
                            borderRadius=BorderRadius.circular(16),
                            hoverColor=color_scheme.onSurface.withOpacity(0.08),
                            child=Container(
                                padding=EdgeInsets.all(7),
                                child=Icon(
                                    Icons.delete_outline,
                                    size=17,
                                    color=color_scheme.onSurfaceVariant,
                                ),
                            ),
                        ),
                    ),
                ],
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        templates = self.widget.chats.templates
        children = [
            Text(
                "Templates",
                style=TextStyle(
                    fontSize=18,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurface,
                ),
            ),
            SizedBox(height=4),
            Text(
                (
                    "Templates save a chat history, title, selected model, "
                    "environments, skills, MCP servers, current input, "
                    "and attachments."
                ),
                style=TextStyle(fontSize=12, color=color_scheme.onSurfaceVariant),
            ),
            SizedBox(height=16),
        ]
        if templates:
            children.extend(
                self._template_row(color_scheme, item) for item in templates
            )
        else:
            children.append(
                Container(
                    padding=EdgeInsets.all(16),
                    decoration=BoxDecoration(
                        color=color_scheme.surfaceContainerLowest,
                        borderRadius=BorderRadius.circular(8),
                        border=Border.all(width=1, color=color_scheme.outlineVariant),
                    ),
                    child=Text(
                        "No templates saved yet.",
                        style=TextStyle(
                            fontSize=13,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                )
            )
        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=children,
        )


class _DeleteTemplateConfirmDialog(StatelessWidget):
    def __init__(self, *, label, on_cancel, on_confirm, key=None):
        super().__init__(key=key)
        self.label = label
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
                        f'"{self.label}" will be permanently removed.',
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
            title="Delete template?",
            leading_icon=Icons.delete_outline,
            mode="fit_content",
            on_close=self.on_cancel,
            body=body,
        )
