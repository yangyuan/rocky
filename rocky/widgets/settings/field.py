from flut.dart.ui import FontWeight
from flut.flutter.material import TextField, Theme
from flut.flutter.material.input_border import InputBorder
from flut.flutter.material.input_decorator import InputDecoration
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment
from flut.flutter.widgets import (
    Column,
    Container,
    SizedBox,
    State,
    StatefulWidget,
    Text,
    TextEditingController,
)


class RockySettingsField(StatefulWidget):
    def __init__(
        self,
        *,
        label,
        value,
        on_changed,
        hint_text=None,
        helper=None,
        obscure=False,
        key=None,
    ):
        super().__init__(key=key)
        self.label = label
        self.value = value or ""
        self.on_changed = on_changed
        self.hint_text = hint_text
        self.helper = helper
        self.obscure = obscure

    def createState(self):
        return _RockySettingsFieldState()


class _RockySettingsFieldState(State[RockySettingsField]):
    def initState(self):
        self._controller = TextEditingController(text=self.widget.value)

    def dispose(self):
        self._controller.dispose()

    def _submit(self, value):
        self.widget.on_changed((value or "").strip())

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        children = [
            Text(
                self.widget.label,
                style=TextStyle(
                    fontSize=12,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
            SizedBox(height=6),
            Container(
                decoration=BoxDecoration(
                    color=color_scheme.surfaceContainerLowest,
                    borderRadius=BorderRadius.circular(8),
                    border=Border.all(width=1, color=color_scheme.outlineVariant),
                ),
                padding=EdgeInsets.symmetric(horizontal=10, vertical=2),
                child=TextField(
                    controller=self._controller,
                    obscureText=self.widget.obscure,
                    onSubmitted=self._submit,
                    onChanged=self._submit,
                    style=TextStyle(
                        fontSize=13,
                        color=color_scheme.onSurface,
                    ),
                    cursorColor=color_scheme.primary,
                    decoration=InputDecoration(
                        hintText=self.widget.hint_text,
                        hintStyle=TextStyle(
                            fontSize=13,
                            color=color_scheme.onSurfaceVariant.withOpacity(0.7),
                        ),
                        isDense=True,
                        contentPadding=EdgeInsets.symmetric(horizontal=2, vertical=10),
                        border=InputBorder.none,
                        enabledBorder=InputBorder.none,
                        focusedBorder=InputBorder.none,
                        disabledBorder=InputBorder.none,
                    ),
                ),
            ),
        ]
        helper_text = self.widget.helper if self.widget.helper else " "
        helper_color = (
            color_scheme.onSurfaceVariant
            if self.widget.helper
            else color_scheme.onSurfaceVariant.withOpacity(0)
        )
        children.extend(
            [
                SizedBox(height=4),
                Text(
                    helper_text,
                    style=TextStyle(fontSize=11, color=helper_color),
                ),
            ]
        )
        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=children,
        )
