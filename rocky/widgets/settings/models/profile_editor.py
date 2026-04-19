import uuid
from typing import Optional

from flut.dart.ui import FontWeight
from flut.flutter.material import (
    Colors,
    Dialog,
    ElevatedButton,
    Icons,
    InkWell,
    Material,
    OutlinedButton,
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
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment, MainAxisSize
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
    Wrap,
)
from flut.flutter.widgets.navigator import Navigator
from flut.flutter.foundation.key import ValueKey

from rocky.contracts.model import RockyModelProfile
from rocky.models.templates import RockyModelTemplates
from rocky.system import RockySystem
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.field import RockySettingsField
from rocky.widgets.settings.models.provider_picker import RockyProviderPicker


class RockyModelProfileEditor(StatefulWidget):
    def __init__(
        self,
        *,
        on_save,
        on_cancel,
        initial: Optional[RockyModelProfile] = None,
        key=None,
    ):
        super().__init__(key=key)
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.initial = initial

    def createState(self):
        return _RockyModelProfileEditorState()


class _RockyModelProfileEditorState(State[RockyModelProfileEditor]):
    def initState(self):
        initial = self.widget.initial
        if initial is None:
            self.profile_id: Optional[str] = None
            self.display_name = ""
            self.display_name_overridden = False
            self.provider = "openai"
            recommended = RockyModelTemplates.recommended(self.provider)
            self.name = recommended.name if recommended else ""
            self.key = ""
            self.endpoint = ""
            self.deployment = ""
        else:
            self.profile_id = initial.id
            self.display_name = initial.display_name
            self.provider = initial.provider
            self.name = initial.name
            self.key = initial.key
            self.endpoint = initial.endpoint
            self.deployment = initial.deployment
            self.display_name_overridden = (
                bool((initial.display_name or "").strip())
                and initial.display_name.strip() != self._derived_display_name()
            )
        self.error: str | None = None
        self._name_field_revision = 0

    @property
    def is_edit(self) -> bool:
        return self.profile_id is not None

    def _derived_display_name(self) -> str:
        provider_label = RockyModelTemplates.label(self.provider)
        if self.provider == "litertlm":
            return provider_label
        name = (self.name or "").strip()
        if not name:
            return provider_label
        template = RockyModelTemplates.find(self.provider, name)
        model_label = template.label if template is not None else name
        return f"{provider_label} {model_label}"

    def _effective_display_name(self) -> str:
        if self.display_name_overridden:
            typed = (self.display_name or "").strip()
            if typed:
                return typed
        return self._derived_display_name()

    def _set_provider(self, provider):
        if provider == "litertlm" and not RockySystem.is_litert_lm_installed():
            self._show_litertlm_warning(
                on_continue=lambda: self._apply_provider(provider),
            )
            return
        self._apply_provider(provider)

    def _apply_provider(self, provider):
        def _apply():
            self.provider = provider
            recommended = RockyModelTemplates.recommended(provider)
            if provider == "litertlm":
                self.name = ""
            else:
                self.name = recommended.name if recommended else ""
            self.endpoint = ""
            self.deployment = ""
            self.error = None

        self.setState(_apply)

    def _show_litertlm_warning(self, *, on_continue):
        context = self.context
        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=_LiteRtLmMissingDialog(
                    on_cancel=lambda: Navigator.pop(dialog_context),
                    on_continue=lambda: (
                        Navigator.pop(dialog_context),
                        on_continue(),
                    ),
                ),
            ),
        )

    def _set_display_name(self, value):
        self.display_name = value
        self.display_name_overridden = bool((value or "").strip())

    def _set_name(self, value):
        def _apply():
            self.name = value

        self.setState(_apply)

    def _set_key(self, value):
        self.key = value

    def _set_endpoint(self, value):
        self.endpoint = value

    def _set_deployment(self, value):
        self.deployment = value

    def _set_error(self, message):
        def _apply():
            self.error = message

        self.setState(_apply)

    def _pick_template(self, value):
        def _apply():
            self.name = value
            self._name_field_revision += 1

        self.setState(_apply)

    def _submit(self):
        display = self._effective_display_name().strip()
        if not display:
            self._set_error("Display name is required.")
            return
        if not (self.name or "").strip() and self.provider == "litertlm":
            self._set_error("Please choose a model file path.")
            return
        if not (self.name or "").strip():
            self._set_error("Please choose a model.")
            return
        if self.provider != "litertlm" and not (self.key or "").strip():
            self._set_error("API key is required.")
            return
        if self.provider == "azure_openai" and not (self.endpoint or "").strip():
            self._set_error("Endpoint is required.")
            return
        if self.provider == "litertlm" and not RockySystem.is_litert_lm_installed():
            self._show_litertlm_warning(on_continue=self._save)
            return
        self._save()

    def _save(self):
        profile = RockyModelProfile(
            id=self.profile_id or uuid.uuid4().hex,
            display_name=self._effective_display_name().strip(),
            provider=self.provider,
            name=(self.name or "").strip(),
            key=self.key,
            endpoint=(self.endpoint or "").strip(),
            deployment=(self.deployment or "").strip(),
        )
        self.widget.on_save(profile)

    def _browse_litertlm_file(self):
        path = RockySystem.tk_select_file_with_types(
            title="Select a LiteRT-LM model file",
            filetypes=[
                ("LiteRT-LM model", "*.litertlm"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        def _apply():
            self.name = path
            self.error = None

        self.setState(_apply)

    def _quick_pick_chip(self, color_scheme, template):
        selected = template.name == self.name
        background = (
            color_scheme.primary.withOpacity(0.10)
            if selected
            else color_scheme.surfaceContainerLowest
        )
        border_color = (
            color_scheme.primary.withOpacity(0.6)
            if selected
            else color_scheme.outlineVariant
        )
        foreground = color_scheme.primary if selected else color_scheme.onSurface
        return Material(
            color=Colors.transparent,
            child=InkWell(
                onTap=lambda v=template.name: self._pick_template(v),
                borderRadius=BorderRadius.circular(999),
                hoverColor=color_scheme.onSurface.withOpacity(0.04),
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=10, vertical=5),
                    decoration=BoxDecoration(
                        color=background,
                        borderRadius=BorderRadius.circular(999),
                        border=Border.all(width=1, color=border_color),
                    ),
                    child=Text(
                        template.label or template.name,
                        style=TextStyle(
                            fontSize=12,
                            fontWeight=FontWeight.w500,
                            color=foreground,
                        ),
                    ),
                ),
            ),
        )

    def _quick_picks(self, color_scheme, templates):
        if not templates:
            return SizedBox(height=0)
        return Wrap(
            spacing=6,
            runSpacing=6,
            children=[self._quick_pick_chip(color_scheme, t) for t in templates],
        )

    def _provider_specific(self, color_scheme):
        if self.provider == "litertlm":
            return [
                Row(
                    crossAxisAlignment=CrossAxisAlignment.end,
                    children=[
                        Expanded(
                            child=RockySettingsField(
                                key=ValueKey("litertlm-file"),
                                label="LiteRT-LM model file",
                                value=self.name,
                                on_changed=self._set_name,
                                hint_text=r"C:\path\to\model.litertlm",
                            ),
                        ),
                        SizedBox(width=8),
                        Container(
                            padding=EdgeInsets.only(bottom=22),
                            child=OutlinedButton(
                                onPressed=self._browse_litertlm_file,
                                child=Row(
                                    mainAxisSize=MainAxisSize.min,
                                    children=[
                                        Icon(Icons.folder_open, size=16),
                                        SizedBox(width=6),
                                        Text("Browse\u2026"),
                                    ],
                                ),
                            ),
                        ),
                    ],
                ),
            ]

        templates = RockyModelTemplates.all(self.provider)
        children = [
            RockySettingsField(
                key=ValueKey(f"api-key-{self.provider}"),
                label="API key",
                value=self.key,
                on_changed=self._set_key,
                hint_text="sk-...",
                helper=(
                    "Stored locally in config.json."
                    if self.provider == "openai"
                    else "Stored locally in config.json. Sent only to your Azure endpoint."
                ),
                obscure=True,
            ),
        ]

        if self.provider == "azure_openai":
            children.extend(
                [
                    SizedBox(height=14),
                    RockySettingsField(
                        key=ValueKey(f"endpoint-{self.provider}"),
                        label="Endpoint",
                        value=self.endpoint,
                        on_changed=self._set_endpoint,
                        hint_text="https://my-resource.openai.azure.com",
                    ),
                ]
            )

        children.extend(
            [
                SizedBox(height=18),
                RockySettingsField(
                    key=ValueKey(
                        f"model-name-{self.provider}-{self._name_field_revision}"
                    ),
                    label="Model",
                    value=self.name,
                    on_changed=self._set_name,
                    hint_text="gpt-5.4",
                    helper="Type any model identifier, or pick a suggestion below.",
                ),
                SizedBox(height=8),
                self._quick_picks(color_scheme, templates),
            ]
        )

        if self.provider == "azure_openai":
            children.extend(
                [
                    SizedBox(height=14),
                    RockySettingsField(
                        key=ValueKey(f"deployment-{self.provider}"),
                        label="Deployment name (optional)",
                        value=self.deployment,
                        on_changed=self._set_deployment,
                        hint_text="Defaults to the model name above",
                        helper="Override if your Azure deployment name differs from the model.",
                    ),
                ]
            )

        return children

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme

        save_label = "Save changes" if self.is_edit else "Save model"

        display_key = (
            ValueKey("display-name-overridden")
            if self.display_name_overridden
            else ValueKey(f"display-name-derived-{self._derived_display_name()}")
        )

        children = [
            RockySettingsField(
                key=display_key,
                label="Display name",
                value=self._effective_display_name(),
                on_changed=self._set_display_name,
                hint_text="My GPT-5.4",
                helper="Shown in the chat header and model list.",
            ),
            SizedBox(height=18),
            Text(
                "Provider",
                style=TextStyle(
                    fontSize=12,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
            SizedBox(height=6),
            RockyProviderPicker(
                value=self.provider,
                on_changed=self._set_provider,
            ),
            SizedBox(height=18),
            *self._provider_specific(color_scheme),
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
                                fontSize=12,
                                color=color_scheme.onErrorContainer,
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
                        ElevatedButton(
                            onPressed=self._submit,
                            child=Text(save_label),
                        ),
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


class _LiteRtLmMissingDialog(StatelessWidget):
    def __init__(self, *, on_cancel, on_continue, key=None):
        super().__init__(key=key)
        self.on_cancel = on_cancel
        self.on_continue = on_continue

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        body = Container(
            width=420,
            padding=EdgeInsets.all(20),
            child=Column(
                mainAxisSize=MainAxisSize.min,
                crossAxisAlignment=CrossAxisAlignment.start,
                children=[
                    Text(
                        "To run LiteRT-LM models, install the runtime:",
                        style=TextStyle(
                            fontSize=12,
                            color=color_scheme.onSurface,
                        ),
                    ),
                    SizedBox(height=8),
                    Container(
                        padding=EdgeInsets.symmetric(horizontal=10, vertical=8),
                        decoration=BoxDecoration(
                            color=color_scheme.surfaceContainerHighest,
                            borderRadius=BorderRadius.circular(6),
                        ),
                        child=Text(
                            "pip install litert-lm",
                            style=TextStyle(
                                fontSize=12,
                                color=color_scheme.onSurface,
                            ),
                        ),
                    ),
                    SizedBox(height=10),
                    Text(
                        "You can continue and configure the profile now; chats will be unavailable until the runtime is installed.",
                        style=TextStyle(
                            fontSize=12,
                            color=color_scheme.onSurfaceVariant,
                        ),
                    ),
                    SizedBox(height=20),
                    Row(
                        mainAxisAlignment=MainAxisAlignment.end,
                        children=[
                            OutlinedButton(
                                onPressed=self.on_cancel,
                                child=Text("Cancel"),
                            ),
                            SizedBox(width=10),
                            ElevatedButton(
                                onPressed=self.on_continue,
                                child=Text("Continue anyway"),
                            ),
                        ],
                    ),
                ],
            ),
        )
        return RockyDialog(
            title="LiteRT-LM is not installed",
            leading_icon=Icons.info_outline,
            mode="fit_content",
            on_close=self.on_cancel,
            body=body,
        )
