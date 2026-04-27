from flut.dart.ui import FontWeight, TextAlign
from flut.flutter.material import Colors, InkWell, Material, Theme, Tooltip
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.widgets import (
    Container,
    Expanded,
    Row,
    StatelessWidget,
    Text,
)

from rocky.contracts.model import RockyModelProviderName
from rocky.models.templates import RockyModelTemplates


class RockyProviderPicker(StatelessWidget):
    def __init__(
        self,
        *,
        value,
        on_changed,
        disabled_providers: dict[RockyModelProviderName, str] | None = None,
        key=None,
    ):
        super().__init__(key=key)
        self.value = value
        self.on_changed = on_changed
        self.disabled_providers = disabled_providers or {}

    def _segment(self, color_scheme, provider, is_first, is_last):
        selected = provider == self.value
        disabled_reason = self.disabled_providers.get(provider)
        is_disabled = disabled_reason is not None
        if is_disabled:
            background = color_scheme.surfaceContainerHighest
            foreground = color_scheme.onSurfaceVariant.withOpacity(0.5)
        elif selected:
            background = color_scheme.primary.withOpacity(0.10)
            foreground = color_scheme.primary
        else:
            background = Colors.transparent
            foreground = color_scheme.onSurfaceVariant
        radius = BorderRadius(
            topLeft=8 if is_first else 0,
            bottomLeft=8 if is_first else 0,
            topRight=8 if is_last else 0,
            bottomRight=8 if is_last else 0,
        )
        segment = Material(
            color=Colors.transparent,
            child=InkWell(
                onTap=(
                    None if is_disabled else (lambda p=provider: self.on_changed(p))
                ),
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.04),
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=12, vertical=8),
                    decoration=BoxDecoration(color=background, borderRadius=radius),
                    child=Text(
                        RockyModelTemplates.label(provider),
                        textAlign=TextAlign.center,
                        style=TextStyle(
                            fontSize=12,
                            fontWeight=(
                                FontWeight.w600 if selected else FontWeight.w500
                            ),
                            color=foreground,
                        ),
                    ),
                ),
            ),
        )
        if is_disabled:
            segment = Tooltip(message=disabled_reason, child=segment)
        return Expanded(child=segment)

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        providers = RockyModelTemplates.providers()
        last = len(providers) - 1
        children = [
            self._segment(color_scheme, provider, i == 0, i == last)
            for i, provider in enumerate(providers)
        ]
        return Container(
            decoration=BoxDecoration(
                borderRadius=BorderRadius.circular(8),
                border=Border.all(width=1, color=color_scheme.outlineVariant),
            ),
            child=Row(children=children),
        )
