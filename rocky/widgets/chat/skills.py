from __future__ import annotations

from typing import Callable

from flut.dart.ui import FontWeight
from flut.flutter.material import (
    Checkbox,
    Colors,
    Dialog,
    Icons,
    InkWell,
    Material,
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
from flut.flutter.rendering import CrossAxisAlignment, MainAxisSize
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Row,
    SingleChildScrollView,
    SizedBox,
    State,
    StatefulWidget,
    Text,
)

from rocky.agentic.contracts.skill import Skill, SkillSource
from rocky.widgets.dialog import RockyDialog


class RockyChatSkillsDialog(StatefulWidget):
    def __init__(
        self,
        *,
        skills: list[Skill],
        selected_skill_ids: list[str],
        on_set_skill_selected: Callable[[str, bool], None],
        key=None,
    ):
        super().__init__(key=key)
        self.skills = list(skills)
        self.selected_skill_ids = list(selected_skill_ids)
        self.on_set_skill_selected = on_set_skill_selected

    @staticmethod
    def open(
        context,
        *,
        skills: list[Skill],
        selected_skill_ids: list[str],
        on_set_skill_selected: Callable[[str, bool], None],
    ) -> None:
        showDialog(
            context=context,
            barrierColor=Colors.grey800.withOpacity(0.8),
            builder=lambda dialog_context: Dialog(
                backgroundColor=Colors.transparent,
                insetPadding=EdgeInsets.all(40),
                child=RockyChatSkillsDialog(
                    skills=skills,
                    selected_skill_ids=selected_skill_ids,
                    on_set_skill_selected=on_set_skill_selected,
                ),
            ),
        )

    def createState(self):
        return _RockyChatSkillsDialogState()


class _RockyChatSkillsDialogState(State[RockyChatSkillsDialog]):
    def initState(self):
        self._selected_skill_ids = list(self.widget.selected_skill_ids)

    def _toggle(self, skill: Skill, selected: bool) -> None:
        skill_ids = list(self._selected_skill_ids)
        already_selected = skill.id in skill_ids
        if selected and not already_selected:
            skill_ids.append(skill.id)
        elif not selected and already_selected:
            skill_ids = [skill_id for skill_id in skill_ids if skill_id != skill.id]
        else:
            return

        def _apply():
            self._selected_skill_ids = skill_ids

        self.setState(_apply)
        self.widget.on_set_skill_selected(skill.id, selected)

    def _skill_row(self, color_scheme, skill: Skill):
        selected = skill.id in self._selected_skill_ids
        radius = BorderRadius.circular(8)
        return Material(
            color=color_scheme.surfaceContainerLowest,
            borderRadius=radius,
            child=InkWell(
                onTap=lambda: self._toggle(skill, not selected),
                borderRadius=radius,
                hoverColor=color_scheme.onSurface.withOpacity(0.04),
                child=Container(
                    padding=EdgeInsets.fromLTRB(8, 8, 12, 8),
                    decoration=BoxDecoration(
                        borderRadius=radius,
                        border=Border.all(width=1, color=color_scheme.outlineVariant),
                    ),
                    child=Row(
                        mainAxisSize=MainAxisSize.max,
                        children=[
                            Checkbox(
                                value=selected,
                                onChanged=lambda value: self._toggle(
                                    skill, bool(value)
                                ),
                            ),
                            SizedBox(width=8),
                            Expanded(
                                child=Column(
                                    crossAxisAlignment=CrossAxisAlignment.start,
                                    children=[
                                        Text(
                                            skill.name,
                                            style=TextStyle(
                                                fontSize=13,
                                                fontWeight=FontWeight.w600,
                                                color=color_scheme.onSurface,
                                            ),
                                        ),
                                        SizedBox(height=2),
                                        Text(
                                            skill.description,
                                            style=TextStyle(
                                                fontSize=11,
                                                color=color_scheme.onSurfaceVariant,
                                            ),
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ),
            ),
        )

    def _skill_group(self, color_scheme, title: str, source: SkillSource):
        skills = [skill for skill in self.widget.skills if skill.source == source]
        children = [
            Text(
                title,
                style=TextStyle(
                    fontSize=12,
                    fontWeight=FontWeight.w600,
                    color=color_scheme.onSurfaceVariant,
                ),
            ),
            SizedBox(height=6),
        ]
        if skills:
            for skill in skills:
                children.append(self._skill_row(color_scheme, skill))
                children.append(SizedBox(height=8))
        else:
            children.append(
                Text(
                    "No skills found.",
                    style=TextStyle(fontSize=12, color=color_scheme.onSurfaceVariant),
                )
            )
        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=children,
        )

    def build(self, context):
        color_scheme = Theme.of(context).colorScheme
        body = Container(
            width=460,
            height=320,
            padding=EdgeInsets.all(16),
            child=Column(
                crossAxisAlignment=CrossAxisAlignment.stretch,
                children=[
                    Expanded(
                        child=SingleChildScrollView(
                            child=Column(
                                crossAxisAlignment=CrossAxisAlignment.stretch,
                                children=[
                                    self._skill_group(
                                        color_scheme,
                                        "System Skills",
                                        SkillSource.SYSTEM,
                                    ),
                                    SizedBox(height=10),
                                    self._skill_group(
                                        color_scheme,
                                        "User Skills",
                                        SkillSource.USER,
                                    ),
                                ],
                            ),
                        )
                    ),
                ],
            ),
        )
        return RockyDialog(
            title="Skills",
            leading_icon=Icons.extension,
            mode="fit_content",
            body=body,
        )
