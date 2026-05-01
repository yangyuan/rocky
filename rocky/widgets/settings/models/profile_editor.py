import json
import uuid
from typing import Optional

from flut.dart.ui import FontWeight, Radius, TextAlign
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

from rocky.contracts.model import (
    RockyModelApi,
    RockyModelCapability,
    RockyModelProfile,
    RockyModelProviderName,
)
from rocky.models.capabilities import RockyModelCapabilities
from rocky.models.templates import RockyModelTemplates
from rocky.system import RockySystem
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.field import RockySettingsField
from rocky.widgets.settings.models.capabilities import RockyModelCapabilityFields
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
            self.provider = RockyModelProviderName.OPENAI
            self.api = RockyModelApi.CHAT_COMPLETIONS
            recommended = RockyModelTemplates.recommended(self.provider)
            self.name = recommended.name if recommended else ""
            self.capabilities = RockyModelCapabilities.baseline(
                self.provider,
                self.name,
            )
            self.key = ""
            self.endpoint = ""
            self.deployment = ""
            self.headers_text = ""
        else:
            self.profile_id = initial.id
            self.display_name = initial.display_name
            self.provider = initial.provider
            self.api = initial.api
            self.name = initial.name
            self.capabilities = self._initial_capabilities(initial)
            self.key = initial.key
            self.endpoint = initial.endpoint
            self.deployment = initial.deployment
            self.headers_text = self._headers_to_text(initial.headers)
            self.display_name_overridden = (
                bool((initial.display_name or "").strip())
                and initial.display_name.strip() != self._derived_display_name()
            )
        self.error: str | None = None
        self._name_field_revision = 0

    @property
    def is_edit(self) -> bool:
        return self.profile_id is not None

    def _initial_capabilities(
        self,
        initial: RockyModelProfile,
    ) -> list[RockyModelCapability]:
        return RockyModelCapabilities.effective(initial)

    def _derived_display_name(self) -> str:
        provider_label = RockyModelTemplates.label(self.provider)
        if self.provider == RockyModelProviderName.LITERTLM:
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
        if (
            provider == RockyModelProviderName.LITERTLM
            and not RockySystem.is_litert_lm_installed()
        ):
            self._show_litertlm_warning(
                on_continue=lambda: self._apply_provider(provider),
            )
            return
        self._apply_provider(provider)

    def _apply_provider(self, provider):
        def _apply():
            self.provider = provider
            self.api = RockyModelApi.CHAT_COMPLETIONS
            recommended = RockyModelTemplates.recommended(provider)
            if provider == RockyModelProviderName.LITERTLM:
                self.name = ""
            else:
                self.name = recommended.name if recommended else ""
            self.capabilities = RockyModelCapabilities.baseline(
                self.provider,
                self.name,
            )
            self.endpoint = ""
            self.deployment = ""
            self.headers_text = ""
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

    def _set_api(self, value):
        def _apply():
            self.api = value

        self.setState(_apply)

    def _set_key(self, value):
        self.key = value

    def _set_endpoint(self, value):
        self.endpoint = value

    def _set_deployment(self, value):
        self.deployment = value

    def _set_headers_text(self, value):
        self.headers_text = value

    def _set_capabilities(self, value: list[RockyModelCapability]):
        def _apply():
            self.capabilities = value

        self.setState(_apply)

    def _set_error(self, message):
        def _apply():
            self.error = message

        self.setState(_apply)

    def _pick_template(self, value):
        def _apply():
            self.name = value
            self.capabilities = RockyModelCapabilities.baseline(
                self.provider,
                value,
            )
            self._name_field_revision += 1

        self.setState(_apply)

    def _submit(self):
        display = self._effective_display_name().strip()
        if not display:
            self._set_error("Display name is required.")
            return
        if (
            not (self.name or "").strip()
            and self.provider == RockyModelProviderName.LITERTLM
        ):
            self._set_error("Please choose a model file path.")
            return
        if not (self.name or "").strip():
            self._set_error("Please choose a model.")
            return
        if (
            self.provider
            not in (
                RockyModelProviderName.LITERTLM,
                RockyModelProviderName.OPENAI_COMPATIBLE,
            )
            and not (self.key or "").strip()
        ):
            self._set_error("API key is required.")
            return
        if (
            self.provider
            in (
                RockyModelProviderName.AZURE_OPENAI,
                RockyModelProviderName.OPENAI_COMPATIBLE,
            )
            and not (self.endpoint or "").strip()
        ):
            self._set_error("Endpoint is required.")
            return
        try:
            self._parse_headers()
        except ValueError as error:
            self._set_error(str(error))
            return
        if (
            self.provider == RockyModelProviderName.LITERTLM
            and not RockySystem.is_litert_lm_installed()
        ):
            self._show_litertlm_warning(on_continue=self._save)
            return
        self._save()

    def _save(self):
        profile = RockyModelProfile(
            id=self.profile_id or uuid.uuid4().hex,
            display_name=self._effective_display_name().strip(),
            provider=self.provider,
            api=self.api,
            name=(self.name or "").strip(),
            capabilities=RockyModelCapabilities.profile_overrides(
                provider=self.provider,
                name=(self.name or "").strip(),
                capabilities=list(self.capabilities),
            ),
            key=self.key,
            endpoint=(self.endpoint or "").strip(),
            deployment=(self.deployment or "").strip(),
            headers=self._parse_headers(),
        )
        self.widget.on_save(profile)

    @staticmethod
    def _headers_to_text(headers: dict[str, str]) -> str:
        return "\n".join(f"{key}: {value}" for key, value in headers.items())

    def _parse_headers(self) -> dict[str, str]:
        text = (self.headers_text or "").strip()
        if not text:
            return {}
        if text.startswith("{"):
            try:
                value = json.loads(text)
            except json.JSONDecodeError as error:
                raise ValueError("Custom headers must be valid JSON.") from error
            if not isinstance(value, dict):
                raise ValueError("Custom headers JSON must be an object.")
            return {str(key): str(item) for key, item in value.items()}

        headers: dict[str, str] = {}
        for line in text.splitlines():
            item = line.strip()
            if not item:
                continue
            if ":" not in item:
                raise ValueError("Custom headers must use Name: value lines.")
            key, value = item.split(":", 1)
            key = key.strip()
            if not key:
                raise ValueError("Custom header names cannot be empty.")
            headers[key] = value.strip()
        return headers

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
            self.capabilities = RockyModelCapabilities.baseline(
                self.provider,
                self.name,
            )
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

    def _api_segment(self, color_scheme, api, is_first, is_last):
        selected = api == self.api
        background = (
            color_scheme.primary.withOpacity(0.10) if selected else Colors.transparent
        )
        foreground = color_scheme.primary if selected else color_scheme.onSurfaceVariant
        radius = BorderRadius(
            topLeft=Radius.circular(8) if is_first else Radius.zero,
            bottomLeft=Radius.circular(8) if is_first else Radius.zero,
            topRight=Radius.circular(8) if is_last else Radius.zero,
            bottomRight=Radius.circular(8) if is_last else Radius.zero,
        )
        return Expanded(
            child=Material(
                color=Colors.transparent,
                child=InkWell(
                    onTap=lambda value=api: self._set_api(value),
                    borderRadius=radius,
                    hoverColor=color_scheme.onSurface.withOpacity(0.04),
                    child=Container(
                        padding=EdgeInsets.symmetric(horizontal=12, vertical=8),
                        decoration=BoxDecoration(color=background, borderRadius=radius),
                        child=Text(
                            RockyModelTemplates.api_label(api),
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
        )

    def _api_selector(self, color_scheme):
        apis = (RockyModelApi.CHAT_COMPLETIONS, RockyModelApi.RESPONSES)
        last = len(apis) - 1
        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=[
                Text(
                    "OpenAI API",
                    style=TextStyle(
                        fontSize=12,
                        fontWeight=FontWeight.w600,
                        color=color_scheme.onSurfaceVariant,
                    ),
                ),
                SizedBox(height=6),
                Container(
                    decoration=BoxDecoration(
                        borderRadius=BorderRadius.circular(8),
                        border=Border.all(width=1, color=color_scheme.outlineVariant),
                    ),
                    child=Row(
                        children=[
                            self._api_segment(color_scheme, api, i == 0, i == last)
                            for i, api in enumerate(apis)
                        ],
                    ),
                ),
            ],
        )

    def _provider_specific(self, color_scheme):
        if self.provider == RockyModelProviderName.LITERTLM:
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
                        OutlinedButton(
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
                    ],
                ),
            ]

        templates = RockyModelTemplates.all(self.provider)
        provider_name = self.provider.value
        is_compatible = self.provider == RockyModelProviderName.OPENAI_COMPATIBLE
        children = [
            self._api_selector(color_scheme),
            SizedBox(height=14),
            RockySettingsField(
                key=ValueKey(f"api-key-{provider_name}"),
                label="Bearer token (optional)" if is_compatible else "API key",
                value=self.key,
                on_changed=self._set_key,
                hint_text="sk-..." if not is_compatible else "Optional token",
                helper=(
                    "Sends Authorization: Bearer when filled. Leave empty if auth "
                    "uses custom headers."
                    if is_compatible
                    else (
                        "Stored locally in config.json."
                        if self.provider == RockyModelProviderName.OPENAI
                        else "Stored locally in config.json. Sent only to your Azure endpoint."
                    )
                ),
                obscure=True,
            ),
        ]

        if self.provider in (
            RockyModelProviderName.AZURE_OPENAI,
            RockyModelProviderName.OPENAI_COMPATIBLE,
        ):
            children.extend(
                [
                    SizedBox(height=14),
                    RockySettingsField(
                        key=ValueKey(f"endpoint-{provider_name}"),
                        label="Base URL" if is_compatible else "Endpoint",
                        value=self.endpoint,
                        on_changed=self._set_endpoint,
                        hint_text=(
                            "http://localhost:8000/v1"
                            if is_compatible
                            else "https://my-resource.openai.azure.com"
                        ),
                        helper=(
                            "Use the base URL documented by the endpoint, usually "
                            "ending in /v1."
                            if is_compatible
                            else None
                        ),
                    ),
                ]
            )

        children.extend(
            [
                SizedBox(height=18),
                RockySettingsField(
                    key=ValueKey(
                        f"model-name-{provider_name}-{self._name_field_revision}"
                    ),
                    label="Model",
                    value=self.name,
                    on_changed=self._set_name,
                    hint_text=("model-name" if is_compatible else "gpt-5.4"),
                    helper=(
                        "Type the model identifier served by this endpoint."
                        if is_compatible
                        else "Type any model identifier, or pick a suggestion below."
                    ),
                ),
            ]
        )
        if not is_compatible:
            children.extend(
                [
                    SizedBox(height=8),
                    self._quick_picks(color_scheme, templates),
                ]
            )

        if is_compatible:
            children.extend(
                [
                    SizedBox(height=14),
                    RockySettingsField(
                        key=ValueKey(f"headers-{provider_name}"),
                        label="Custom headers",
                        value=self.headers_text,
                        on_changed=self._set_headers_text,
                        hint_text="Header-Name: value",
                        helper=(
                            "Add only headers required by the endpoint; use "
                            "Name: value lines or a JSON object."
                        ),
                        min_lines=2,
                        max_lines=4,
                    ),
                ]
            )

        if self.provider == RockyModelProviderName.AZURE_OPENAI:
            children.extend(
                [
                    SizedBox(height=14),
                    RockySettingsField(
                        key=ValueKey(f"deployment-{provider_name}"),
                        label="Deployment name (optional)",
                        value=self.deployment,
                        on_changed=self._set_deployment,
                        hint_text="Defaults to the model name above",
                        helper="Override if your Azure deployment name differs from the model.",
                    ),
                ]
            )

        return children

    def _capability_fields(self):
        if not self.capabilities:
            return []
        return [
            SizedBox(height=18),
            RockyModelCapabilityFields(
                definitions=RockyModelCapabilities.definitions(),
                capabilities=self.capabilities,
                on_changed=self._set_capabilities,
            ),
        ]

    def _provider_description(self, color_scheme):
        if self.provider != RockyModelProviderName.OPENAI_COMPATIBLE:
            return []
        return [
            SizedBox(height=6),
            Text(
                "For endpoints that implement OpenAI Chat Completions or Responses "
                "APIs, such as vLLM, llama.cpp, LM Studio, Ollama, OpenRouter, "
                "Together AI, Groq, or DashScope.",
                style=TextStyle(
                    fontSize=11,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
        ]

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
            *self._provider_description(color_scheme),
            SizedBox(height=18),
            *self._provider_specific(color_scheme),
            *self._capability_fields(),
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
