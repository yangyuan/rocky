from flut.dart.ui import FontWeight
from flut.flutter.material import Icons, Theme
from flut.flutter.painting import EdgeInsets, TextStyle
from flut.flutter.rendering import CrossAxisAlignment, MainAxisSize
from flut.flutter.widgets import Column, Container, SizedBox, StatelessWidget, Text

from rocky.widgets.dialog import RockyDialog


class RockyAboutDialog(StatelessWidget):
    def __init__(self, *, key=None):
        super().__init__(key=key)

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        body = Container(
            width=360,
            padding=EdgeInsets.all(20),
            child=Column(
                mainAxisSize=MainAxisSize.min,
                crossAxisAlignment=CrossAxisAlignment.start,
                children=[
                    Text(
                        "Rocky",
                        style=TextStyle(
                            fontSize=22,
                            fontWeight=FontWeight.bold,
                            color=color_scheme.onSurface,
                        ),
                    ),
                    SizedBox(height=16),
                    Text(
                        "An Open Source Desktop Agent.",
                        style=TextStyle(
                            fontSize=12,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                    SizedBox(height=16),
                    Text(
                        "Built with Python, Flut and the OpenAI Agents SDK.",
                        style=TextStyle(
                            fontSize=12,
                            height=1.4,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                    SizedBox(height=12),
                    Text(
                        "\u00a9 2026 rockstudio.org",
                        style=TextStyle(
                            fontSize=11,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                    SizedBox(height=2),
                    Text(
                        "MIT License",
                        style=TextStyle(
                            fontSize=11,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                ],
            ),
        )

        return RockyDialog(
            title="About Rocky",
            leading_icon=Icons.info_outline,
            mode="fit_content",
            body=body,
        )
