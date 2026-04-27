from flut.dart.ui import FontWeight
from flut.flutter.material import Checkbox, InkWell, Material, Theme
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisSize
from flut.flutter.widgets import Column, Container, Row, SizedBox, StatelessWidget, Text

from rocky.contracts.model import (
    RockyModelCapability,
    RockyModelCapabilityDefinition,
    RockyModelCapabilityType,
)
from rocky.models.capabilities import RockyModelCapabilities


class RockyModelCapabilityFields(StatelessWidget):
    def __init__(
        self,
        *,
        definitions: list[RockyModelCapabilityDefinition],
        capabilities: list[RockyModelCapability],
        on_changed,
        key=None,
    ):
        super().__init__(key=key)
        self.definitions = definitions
        self.capabilities = capabilities
        self.on_changed = on_changed

    def _set_bool(self, definition: RockyModelCapabilityDefinition, value: bool | None):
        self.on_changed(
            RockyModelCapabilities.with_value(
                self.capabilities,
                definition.name,
                RockyModelCapabilities.typed_value(definition, bool(value)),
            )
        )

    def _label(self, definition: RockyModelCapabilityDefinition) -> str:
        return definition.label

    def _bool_row(self, color_scheme, definition: RockyModelCapabilityDefinition):
        value = RockyModelCapabilities.value(self.capabilities, definition.name)
        checked = value if isinstance(value, bool) else False
        radius = BorderRadius.circular(8)
        return Material(
            color=color_scheme.surfaceContainerLowest,
            borderRadius=radius,
            child=InkWell(
                onTap=lambda: self._set_bool(
                    definition,
                    not checked,
                ),
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.04),
                child=Container(
                    padding=EdgeInsets.fromLTRB(8, 6, 12, 6),
                    decoration=BoxDecoration(
                        borderRadius=radius,
                        border=Border.all(width=1, color=color_scheme.outlineVariant),
                    ),
                    child=Row(
                        mainAxisSize=MainAxisSize.min,
                        children=[
                            Checkbox(
                                value=checked,
                                onChanged=lambda value: self._set_bool(
                                    definition,
                                    value,
                                ),
                            ),
                            SizedBox(width=6),
                            Text(
                                self._label(definition),
                                style=TextStyle(
                                    fontSize=13,
                                    fontWeight=FontWeight.w500,
                                    color=color_scheme.onSurface,
                                ),
                            ),
                        ],
                    ),
                ),
            ),
        )

    def build(self, context):
        bool_definitions = [
            definition
            for definition in self.definitions
            if definition.type == RockyModelCapabilityType.BOOL
        ]
        if not bool_definitions:
            return SizedBox(height=0)

        color_scheme = Theme.of(context).colorScheme
        rows = [
            self._bool_row(color_scheme, definition) for definition in bool_definitions
        ]
        return Column(
            crossAxisAlignment=CrossAxisAlignment.start,
            children=[
                Text(
                    "Capabilities",
                    style=TextStyle(
                        fontSize=12,
                        fontWeight=FontWeight.w600,
                        color=color_scheme.onSurfaceVariant,
                    ),
                ),
                SizedBox(height=6),
                *rows,
            ],
        )
