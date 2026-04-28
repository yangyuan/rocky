import uuid
from typing import Optional

from flut.dart.ui import FontWeight
from flut.flutter.foundation.key import ValueKey
from flut.flutter.material import (
    ElevatedButton,
    OutlinedButton,
    Theme,
)
from flut.flutter.painting import (
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment
from flut.flutter.widgets import (
    Column,
    Container,
    Row,
    SizedBox,
    State,
    StatefulWidget,
    Text,
)

from rocky.contracts.shell import (
    RockyShellProfile,
    RockyShellType,
)
from rocky.widgets.settings.field import RockySettingsField
from rocky.widgets.settings.shells.type_picker import (
    RockyShellTemplates,
    RockyShellTypePicker,
)


class RockyShellProfileEditor(StatefulWidget):
    def __init__(
        self,
        *,
        on_save,
        on_cancel,
        initial: Optional[RockyShellProfile] = None,
        key=None,
    ):
        super().__init__(key=key)
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.initial = initial

    def createState(self):
        return _RockyShellProfileEditorState()


class _RockyShellProfileEditorState(State[RockyShellProfileEditor]):
    def initState(self):
        initial = self.widget.initial
        if initial is None:
            self.profile_id: Optional[str] = None
            self.display_name = ""
            self.display_name_overridden = False
            self.shell_type: RockyShellType = "docker"
            self.name = ""
            self.host = ""
            self.output_max_head_tail = "20000"
        else:
            self.profile_id = initial.id
            self.display_name = initial.display_name
            self.shell_type = initial.shell_type
            self.name = initial.name
            self.host = initial.host
            self.output_max_head_tail = (
                ""
                if initial.output_max_head_tail is None
                else str(initial.output_max_head_tail)
            )
            self.display_name_overridden = (
                bool((initial.display_name or "").strip())
                and initial.display_name.strip() != self._derived_display_name()
            )
        self.error: str | None = None

    @property
    def is_edit(self) -> bool:
        return self.profile_id is not None

    def _derived_display_name(self) -> str:
        return RockyShellTemplates.derived_display_name_for(
            self.shell_type,
            self.name,
            self.host,
        )

    def _effective_display_name(self) -> str:
        if self.display_name_overridden:
            typed = (self.display_name or "").strip()
            if typed:
                return typed
        return self._derived_display_name()

    def _set_display_name(self, value):
        self.display_name = value
        self.display_name_overridden = bool((value or "").strip())

    def _set_shell_type(self, value: RockyShellType):
        def _apply():
            self.shell_type = value
            self.error = None

        self.setState(_apply)

    def _set_name(self, value):
        def _apply():
            self.name = value

        self.setState(_apply)

    def _set_host(self, value):
        def _apply():
            self.host = value

        self.setState(_apply)

    def _set_output_max_head_tail(self, value):
        self.output_max_head_tail = value

    def _set_error(self, message):
        def _apply():
            self.error = message

        self.setState(_apply)

    def _submit(self):
        display = self._effective_display_name().strip()
        if not display:
            self._set_error("Display name is required.")
            return
        name = (self.name or "").strip()
        host = (self.host or "").strip()
        if RockyShellTemplates.requires_name(self.shell_type) and not name:
            self._set_error("Docker name is required.")
            return
        if RockyShellTemplates.requires_host(self.shell_type) and not host:
            self._set_error("Host is required.")
            return
        output_limit = self._output_limit()
        if output_limit == 0:
            self._set_error("Output limit must be empty or greater than 0.")
            return
        profile = RockyShellProfile(
            id=self.profile_id or uuid.uuid4().hex,
            display_name=display,
            shell_type=self.shell_type,
            name=name,
            host=host,
            output_max_head_tail=output_limit,
        )
        self.widget.on_save(profile)

    def _output_limit(self) -> int | None:
        raw_value = (self.output_max_head_tail or "").strip()
        if not raw_value:
            return None
        try:
            value = int(raw_value)
        except ValueError:
            return 0
        if value <= 0:
            return 0
        return value

    def _shell_fields(self):
        children = []
        if RockyShellTemplates.requires_name(self.shell_type):
            children.extend(
                [
                    RockySettingsField(
                        key=ValueKey(f"shell-name-{self.shell_type}"),
                        label="Docker name",
                        value=self.name,
                        on_changed=self._set_name,
                        hint_text="rocky-dev",
                    ),
                    SizedBox(height=14),
                ]
            )
        if RockyShellTemplates.uses_host(self.shell_type):
            children.extend(
                [
                    RockySettingsField(
                        key=ValueKey(f"shell-host-{self.shell_type}"),
                        label=RockyShellTemplates.host_label(self.shell_type),
                        value=self.host,
                        on_changed=self._set_host,
                        hint_text=RockyShellTemplates.host_hint(self.shell_type),
                    ),
                    SizedBox(height=14),
                ]
            )
        return children

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        save_label = "Save changes" if self.is_edit else "Save environment"
        display_key = (
            ValueKey("shell-display-name-overridden")
            if self.display_name_overridden
            else ValueKey(f"shell-display-name-derived-{self._derived_display_name()}")
        )
        children = [
            RockySettingsField(
                key=display_key,
                label="Display name",
                value=self._effective_display_name(),
                on_changed=self._set_display_name,
                hint_text="Work SSH",
            ),
            SizedBox(height=18),
            Text(
                "Type",
                style=TextStyle(
                    fontSize=12,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
            SizedBox(height=6),
            RockyShellTypePicker(
                value=self.shell_type,
                on_changed=self._set_shell_type,
            ),
            SizedBox(height=18),
            *self._shell_fields(),
            RockySettingsField(
                key=ValueKey("shell-output-limit"),
                label="Output head and tail limit",
                value=self.output_max_head_tail,
                on_changed=self._set_output_max_head_tail,
                hint_text="20000",
            ),
        ]
        if self.error:
            children.extend(
                [
                    SizedBox(height=12),
                    Container(
                        padding=EdgeInsets.symmetric(horizontal=10, vertical=8),
                        decoration=BoxDecoration(
                            color=color_scheme.errorContainer,
                            borderRadius=BorderRadius.circular(8),
                        ),
                        child=Text(
                            self.error,
                            style=TextStyle(
                                fontSize=12, color=color_scheme.onErrorContainer
                            ),
                        ),
                    ),
                ]
            )
        children.extend(
            [
                SizedBox(height=18),
                Row(
                    mainAxisAlignment=MainAxisAlignment.end,
                    children=[
                        OutlinedButton(
                            onPressed=self.widget.on_cancel,
                            child=Text("Cancel"),
                        ),
                        SizedBox(width=10),
                        ElevatedButton(onPressed=self._submit, child=Text(save_label)),
                    ],
                ),
            ]
        )
        return Container(
            padding=EdgeInsets.all(16),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=children,
            ),
        )
