from flut.dart.ui import FontWeight
from flut.flutter.material import (
    Colors,
    Dialog,
    Icons,
    InkWell,
    Material,
    Theme,
    showDialog,
)
from flut.flutter.painting import (
    BorderRadius,
    EdgeInsets,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisAlignment, MainAxisSize
from flut.flutter.rendering.box import BoxConstraints
from flut.flutter.widgets import (
    Builder,
    Column,
    ConstrainedBox,
    Container,
    Icon,
    Row,
    SingleChildScrollView,
    SizedBox,
    State,
    StatefulWidget,
    StatelessWidget,
    Text,
)
from flut.flutter.widgets.media_query import MediaQuery
from flut.flutter.widgets.navigator import Navigator

from rocky.contracts.model import RockyModelProfile
from rocky.widgets.dialog import RockyDialog
from rocky.widgets.settings.models.profile_editor import RockyModelProfileEditor
from rocky.widgets.settings.models.profile import RockyModelProfileCard


class RockySettingsModelsPage(StatefulWidget):
    def __init__(
        self,
        *,
        model_profiles,
        default_model_profile_id,
        on_add_model_profile,
        on_update_model_profile,
        on_delete_model_profile,
        on_set_default_model_profile,
        key=None,
    ):
        super().__init__(key=key)
        self.model_profiles = model_profiles
        self.default_model_profile_id = default_model_profile_id
        self.on_add_model_profile = on_add_model_profile
        self.on_update_model_profile = on_update_model_profile
        self.on_delete_model_profile = on_delete_model_profile
        self.on_set_default_model_profile = on_set_default_model_profile

    def createState(self):
        return _RockySettingsModelsPageState()


class _RockySettingsModelsPageState(State[RockySettingsModelsPage]):
    def initState(self):
        if not self.widget.model_profiles:
            self._schedule_open_add()

    def _schedule_open_add(self):
        from flut.flutter.scheduler import SchedulerBinding

        SchedulerBinding.instance.addPostFrameCallback(
            lambda _: self._open_editor(initial=None)
        )

    def _open_add(self):
        self._open_editor(initial=None)

    def _open_edit(self, model_profile_id: str):
        target = next(
            (
                model_profile
                for model_profile in (self.widget.model_profiles or [])
                if model_profile.id == model_profile_id
            ),
            None,
        )
        if target is None:
            return
        self._open_editor(initial=target)

    def _open_editor(self, *, initial: RockyModelProfile | None):
        context = self.context

        def _editor_body(builder_context):
            screen_height = MediaQuery.of(builder_context).size.height
            max_height = max(280.0, screen_height - 160.0)
            return ConstrainedBox(
                constraints=BoxConstraints(maxHeight=max_height, maxWidth=560),
                child=SingleChildScrollView(
                    padding=EdgeInsets.all(8),
                    child=Container(
                        width=520,
                        child=RockyModelProfileEditor(
                            initial=initial,
                            on_save=lambda model_profile: (
                                Navigator.pop(builder_context),
                                self._on_save(
                                    model_profile, is_edit=initial is not None
                                ),
                            ),
                            on_cancel=lambda: Navigator.pop(builder_context),
                        ),
                    ),
                ),
            )

        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=RockyDialog(
                    title="Edit model" if initial is not None else "Add model",
                    leading_icon=(
                        Icons.edit_outlined if initial is not None else Icons.add
                    ),
                    mode="fit_content",
                    on_close=lambda: Navigator.pop(dialog_context),
                    body=Builder(builder=_editor_body),
                ),
            ),
        )

    def _on_save(self, model_profile: RockyModelProfile, *, is_edit: bool):
        if is_edit:
            self.widget.on_update_model_profile(model_profile)
        else:
            self.widget.on_add_model_profile(model_profile)

    def _add_button(self, color_scheme):
        radius = BorderRadius.circular(8)
        return Material(
            color=color_scheme.primaryContainer,
            borderRadius=radius,
            child=InkWell(
                onTap=self._open_add,
                borderRadius=radius,
                hoverColor=color_scheme.onPrimaryContainer.withOpacity(0.06),
                child=Container(
                    padding=EdgeInsets.symmetric(horizontal=12, vertical=7),
                    child=Row(
                        mainAxisSize=MainAxisSize.min,
                        children=[
                            Icon(
                                Icons.add,
                                size=14,
                                color=color_scheme.onPrimaryContainer,
                            ),
                            SizedBox(width=6),
                            Text(
                                "Add model",
                                style=TextStyle(
                                    fontSize=13,
                                    fontWeight=FontWeight.w500,
                                    color=color_scheme.onPrimaryContainer,
                                ),
                            ),
                        ],
                    ),
                ),
            ),
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        model_profiles = self.widget.model_profiles or []
        children = [
            Text(
                "Models",
                style=TextStyle(
                    fontSize=18,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurface,
                ),
            ),
            SizedBox(height=4),
            Text(
                (
                    "Models are OpenAI, Azure OpenAI, LiteRT-LM, or other model profiles Rocky can use to chat and reason with you."
                ),
                style=TextStyle(
                    fontSize=12,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
            SizedBox(height=16),
        ]

        for model_profile in model_profiles:
            children.append(
                RockyModelProfileCard(
                    profile=model_profile,
                    is_default=(
                        model_profile.id == self.widget.default_model_profile_id
                    ),
                    on_select=self.widget.on_set_default_model_profile,
                    on_edit=self._open_edit,
                    on_delete=self._confirm_delete,
                )
            )

        children.append(SizedBox(height=4))
        children.append(
            Row(
                mainAxisAlignment=MainAxisAlignment.end,
                children=[self._add_button(color_scheme)],
            )
        )

        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=children,
        )

    def _confirm_delete(self, model_profile_id: str):
        target = next(
            (
                model_profile
                for model_profile in (self.widget.model_profiles or [])
                if model_profile.id == model_profile_id
            ),
            None,
        )
        if target is None:
            return
        label = target.display_name or "this model"
        showDialog(
            context=self.context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=_DeleteModelConfirmDialog(
                    label=label,
                    on_cancel=lambda: Navigator.pop(dialog_context),
                    on_confirm=lambda: (
                        Navigator.pop(dialog_context),
                        self.widget.on_delete_model_profile(model_profile_id),
                    ),
                ),
            ),
        )


class _DeleteModelConfirmDialog(StatelessWidget):
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
                        style=TextStyle(
                            fontSize=13,
                            color=color_scheme.onSurface,
                        ),
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
            title="Delete model?",
            leading_icon=Icons.delete_outline,
            mode="fit_content",
            on_close=self.on_cancel,
            body=body,
        )
