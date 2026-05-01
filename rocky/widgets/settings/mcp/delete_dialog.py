from flut.dart.ui import FontWeight
from flut.flutter.material import Colors, Icons, InkWell, Material, Theme
from flut.flutter.painting import BorderRadius, EdgeInsets, TextStyle
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment
from flut.flutter.widgets import Column, Container, Row, SizedBox, StatelessWidget, Text

from rocky.widgets.dialog import RockyDialog


class RockyMcpDeleteDialog(StatelessWidget):
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
            title="Delete MCP server?",
            leading_icon=Icons.delete_outline,
            mode="fit_content",
            on_close=self.on_cancel,
            body=body,
        )
