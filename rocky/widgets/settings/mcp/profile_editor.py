import uuid
from typing import Optional

from flut.dart.ui import FontWeight
from flut.flutter.foundation.key import ValueKey
from flut.flutter.material import (
    ElevatedButton,
    IconButton,
    Icons,
    OutlinedButton,
    Theme,
)
from flut.flutter.painting import BorderRadius, BoxDecoration, EdgeInsets, TextStyle
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
    Text,
)

from rocky.contracts.mcp import (
    RockyHttpMcpServerProperties,
    RockyMcpServerProfile,
    RockyMcpServerType,
    RockyStdioMcpServerProperties,
)
from rocky.widgets.settings.field import RockySettingsField
from rocky.widgets.settings.mcp.type_picker import RockyMcpTemplates, RockyMcpTypePicker


class RockyMcpProfileEditor(StatefulWidget):
    def __init__(
        self,
        *,
        on_save,
        on_cancel,
        initial: Optional[RockyMcpServerProfile] = None,
        key=None,
    ):
        super().__init__(key=key)
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.initial = initial

    def createState(self):
        return _RockyMcpProfileEditorState()


class _RockyMcpProfileEditorState(State[RockyMcpProfileEditor]):
    def initState(self):
        initial = self.widget.initial
        if initial is None:
            self.profile_id: Optional[str] = None
            self.display_name = ""
            self.display_name_overridden = False
            self.server_type: RockyMcpServerType = RockyMcpServerType.STDIO
            self.command = ""
            self.url = ""
            self.header_entries: list[tuple[str, str]] = []
            self.timeout = ""
        else:
            self.profile_id = initial.id
            self.display_name = initial.display_name
            self.server_type = initial.server_type
            self.command = ""
            self.url = ""
            self.header_entries = []
            if isinstance(initial.properties, RockyStdioMcpServerProperties):
                self.command = initial.properties.command
            elif isinstance(initial.properties, RockyHttpMcpServerProperties):
                self.url = initial.properties.url
                self.header_entries = list(initial.properties.headers.items())
            self.timeout = "" if initial.timeout is None else str(initial.timeout)
            self.display_name_overridden = (
                bool((initial.display_name or "").strip())
                and initial.display_name.strip() != self._derived_display_name()
            )
        self.error: str | None = None

    @property
    def is_edit(self) -> bool:
        return self.profile_id is not None

    def _target(self) -> str:
        if self.server_type == RockyMcpServerType.STDIO:
            return self.command
        return self.url

    def _derived_display_name(self) -> str:
        return RockyMcpTemplates.derived_display_name_for(
            self.server_type,
            self._target(),
        )

    def _effective_display_name(self) -> str:
        if self.display_name_overridden:
            typed = (self.display_name or "").strip()
            if typed:
                return typed
        return self._derived_display_name()

    def _set_error(self, message):
        def _apply():
            self.error = message

        self.setState(_apply)

    def _set_display_name(self, value):
        self.display_name = value
        self.display_name_overridden = bool((value or "").strip())

    def _set_server_type(self, value: RockyMcpServerType):
        def _apply():
            self.server_type = value
            self.error = None

        self.setState(_apply)

    def _set_command(self, value):
        def _apply():
            self.command = value

        self.setState(_apply)

    def _set_url(self, value):
        def _apply():
            self.url = value

        self.setState(_apply)

    def _set_timeout(self, value):
        self.timeout = value

    def _add_header(self):
        def _apply():
            self.header_entries = [*self.header_entries, ("", "")]

        self.setState(_apply)

    def _delete_header(self, index: int):
        def _apply():
            self.header_entries = [
                entry
                for entry_index, entry in enumerate(self.header_entries)
                if entry_index != index
            ]

        self.setState(_apply)

    def _set_header_name(self, index: int, value: str):
        entries = list(self.header_entries)
        if index >= len(entries):
            return
        _, header_value = entries[index]
        entries[index] = (value, header_value)
        self.header_entries = entries

    def _set_header_value(self, index: int, value: str):
        entries = list(self.header_entries)
        if index >= len(entries):
            return
        header_name, _ = entries[index]
        entries[index] = (header_name, value)
        self.header_entries = entries

    @staticmethod
    def _optional_float(value: str, label: str) -> tuple[float | None, str | None]:
        raw = (value or "").strip()
        if not raw:
            return None, None
        try:
            parsed = float(raw)
        except ValueError:
            return None, f"{label} must be a number."
        if parsed <= 0:
            return None, f"{label} must be greater than 0."
        return parsed, None

    def _submit(self):
        display = self._effective_display_name().strip()
        if not display:
            self._set_error("Display name is required.")
            return
        if (
            self.server_type == RockyMcpServerType.STDIO
            and not (self.command or "").strip()
        ):
            self._set_error("Command is required.")
            return
        if self.server_type == RockyMcpServerType.HTTP and not (self.url or "").strip():
            self._set_error("URL is required.")
            return
        headers, headers_error = self._headers()
        if self.server_type == RockyMcpServerType.HTTP and headers_error:
            self._set_error(headers_error)
            return
        timeout, error = self._optional_float(self.timeout, "Timeout")
        if error:
            self._set_error(error)
            return
        profile = RockyMcpServerProfile(
            id=self.profile_id or uuid.uuid4().hex,
            display_name=display,
            server_type=self.server_type,
            timeout=timeout,
            properties=(
                RockyStdioMcpServerProperties(command=(self.command or "").strip())
                if self.server_type == RockyMcpServerType.STDIO
                else RockyHttpMcpServerProperties(
                    url=(self.url or "").strip(), headers=headers
                )
            ),
        )
        self.widget.on_save(profile)

    def _headers(self) -> tuple[dict[str, str], str | None]:
        headers: dict[str, str] = {}
        for name, value in self.header_entries:
            header_name = (name or "").strip()
            header_value = (value or "").strip()
            if not header_name and not header_value:
                continue
            if not header_name or not header_value:
                return {}, "Header name and value are required."
            if header_name in headers:
                return {}, f"Header {header_name} is duplicated."
            headers[header_name] = header_value
        return headers, None

    def _header_fields(self):
        children = []
        for index, (name, value) in enumerate(self.header_entries):
            children.extend(
                [
                    Row(
                        crossAxisAlignment=CrossAxisAlignment.end,
                        children=[
                            Expanded(
                                child=RockySettingsField(
                                    key=ValueKey(f"mcp-header-name-{index}"),
                                    label="",
                                    value=name,
                                    on_changed=lambda next_value, header_index=index: self._set_header_name(
                                        header_index, next_value
                                    ),
                                    hint_text="Header name",
                                )
                            ),
                            SizedBox(width=10),
                            Expanded(
                                child=RockySettingsField(
                                    key=ValueKey(f"mcp-header-value-{index}"),
                                    label="",
                                    value=value,
                                    on_changed=lambda next_value, header_index=index: self._set_header_value(
                                        header_index, next_value
                                    ),
                                    hint_text="Header value",
                                )
                            ),
                            SizedBox(width=4),
                            IconButton(
                                onPressed=lambda header_index=index: self._delete_header(
                                    header_index
                                ),
                                icon=Icon(Icons.delete_outline, size=18),
                                tooltip="Delete header",
                            ),
                        ],
                    ),
                    SizedBox(height=10),
                ]
            )
        children.append(
            Row(
                mainAxisAlignment=MainAxisAlignment.start,
                children=[
                    OutlinedButton(onPressed=self._add_header, child=Text("Add header"))
                ],
            )
        )
        return children

    def _transport_fields(self):
        if self.server_type == RockyMcpServerType.STDIO:
            return [
                RockySettingsField(
                    key=ValueKey("mcp-command"),
                    label="Command",
                    value=self.command,
                    on_changed=self._set_command,
                    hint_text="npx -y @modelcontextprotocol/server-filesystem",
                )
            ]
        return [
            RockySettingsField(
                key=ValueKey("mcp-url"),
                label="URL",
                value=self.url,
                on_changed=self._set_url,
                hint_text="http://localhost:8000/mcp",
            ),
            SizedBox(height=14),
            *self._header_fields(),
        ]

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        save_label = "Save changes" if self.is_edit else "Save MCP server"
        display_key = (
            ValueKey("mcp-display-name-overridden")
            if self.display_name_overridden
            else ValueKey(f"mcp-display-name-derived-{self._derived_display_name()}")
        )
        children = [
            RockySettingsField(
                key=display_key,
                label="Display name",
                value=self._effective_display_name(),
                on_changed=self._set_display_name,
                hint_text="Filesystem MCP",
            ),
            SizedBox(height=18),
            Text(
                "Transport",
                style=TextStyle(
                    fontSize=12,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
            SizedBox(height=6),
            RockyMcpTypePicker(
                value=self.server_type, on_changed=self._set_server_type
            ),
            SizedBox(height=18),
            *self._transport_fields(),
            SizedBox(height=14),
            RockySettingsField(
                key=ValueKey("mcp-timeout"),
                label="Timeout seconds",
                value=self.timeout,
                on_changed=self._set_timeout,
                hint_text="10",
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
                            onPressed=self.widget.on_cancel, child=Text("Cancel")
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
