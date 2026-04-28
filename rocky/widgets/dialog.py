from flut.dart.ui import FontWeight, Radius
from flut.flutter.material import IconButton, Icons, Theme
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BorderSide,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import (
    CrossAxisAlignment,
    MainAxisAlignment,
    MainAxisSize,
)
from flut.flutter.rendering.box import BoxConstraints
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Icon,
    IntrinsicWidth,
    Row,
    SizedBox,
    StatelessWidget,
    Text,
)
from flut.flutter.widgets.navigator import Navigator
from typing import Literal

CORNER_RADIUS = 12
TITLE_BAR_HEIGHT = 38

RockyDialogMode = Literal["fit_screen", "fit_content"]


class RockyDialog(StatelessWidget):
    def __init__(
        self,
        *,
        title,
        body,
        mode: RockyDialogMode = "fit_screen",
        leading_icon=None,
        on_close=None,
        actions=None,
        key=None,
    ):
        super().__init__(key=key)
        if mode not in ("fit_screen", "fit_content"):
            raise ValueError(f"Unknown RockyDialog mode: {mode!r}")
        self.title = title
        self.body = body
        self.mode = mode
        self.leading_icon = leading_icon
        self.on_close = on_close
        self.actions = actions or []

    def _close(self, context):
        if self.on_close is not None:
            self.on_close()
        else:
            Navigator.pop(context)

    def _title_bar(self, context, color_scheme):
        leading = []
        if self.leading_icon is not None:
            leading.append(
                Icon(
                    self.leading_icon,
                    size=15,
                    color=color_scheme.onSurfaceVariant,
                )
            )
            leading.append(SizedBox(width=8))
        leading.append(
            Text(
                self.title,
                style=TextStyle(
                    fontSize=13,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurface,
                ),
            )
        )

        trailing = list(self.actions)
        trailing.append(
            IconButton(
                icon=Icon(Icons.close, size=16, color=color_scheme.error),
                onPressed=lambda: self._close(context),
                tooltip="Close",
                padding=EdgeInsets.all(6),
                constraints=BoxConstraints(minWidth=28, minHeight=28),
                splashRadius=16,
            )
        )

        return Container(
            height=TITLE_BAR_HEIGHT,
            padding=EdgeInsets.fromLTRB(14, 0, 10, 0),
            decoration=BoxDecoration(
                color=color_scheme.surfaceContainerHigh,
                borderRadius=BorderRadius(
                    topLeft=Radius.circular(CORNER_RADIUS),
                    topRight=Radius.circular(CORNER_RADIUS),
                ),
                border=Border(
                    bottom=BorderSide(width=1, color=color_scheme.outlineVariant)
                ),
            ),
            child=Row(
                crossAxisAlignment=CrossAxisAlignment.center,
                mainAxisAlignment=MainAxisAlignment.spaceBetween,
                children=[
                    Row(
                        mainAxisSize=MainAxisSize.min,
                        crossAxisAlignment=CrossAxisAlignment.center,
                        children=leading,
                    ),
                    Row(
                        mainAxisSize=MainAxisSize.min,
                        crossAxisAlignment=CrossAxisAlignment.center,
                        children=trailing,
                    ),
                ],
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        decoration = BoxDecoration(
            color=color_scheme.surface,
            borderRadius=BorderRadius.circular(CORNER_RADIUS),
            border=Border.all(width=1, color=color_scheme.outlineVariant),
        )

        if self.mode == "fit_content":
            return IntrinsicWidth(
                child=Container(
                    decoration=decoration,
                    child=Column(
                        mainAxisSize=MainAxisSize.min,
                        crossAxisAlignment=CrossAxisAlignment.stretch,
                        children=[
                            self._title_bar(context, color_scheme),
                            self.body,
                        ],
                    ),
                ),
            )

        return Container(
            constraints=BoxConstraints.expand(),
            decoration=decoration,
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=[
                    self._title_bar(context, color_scheme),
                    Expanded(child=self.body),
                ],
            ),
        )
