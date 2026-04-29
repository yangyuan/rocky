from __future__ import annotations

from pathlib import Path

from flut.dart.ui import FontWeight
from flut.flutter.material import Checkbox, Icons, InkWell, Material, TextButton, Theme
from flut.flutter.painting import (
    Border,
    BorderRadius,
    BoxDecoration,
    EdgeInsets,
    TextOverflow,
    TextStyle,
)
from flut.flutter.rendering import CrossAxisAlignment, MainAxisSize
from flut.flutter.widgets import (
    Column,
    Container,
    Expanded,
    Icon,
    Row,
    SizedBox,
    StatelessWidget,
    Text,
)

from rocky.agentic.contracts.skill import Skill, SkillSource
from rocky.system import RockySystem


class RockySettingsSkillsPage(StatelessWidget):
    def __init__(
        self,
        *,
        skills: list[Skill],
        default_skill_ids: list[str],
        system_skills_folder: Path,
        user_skills_folder: Path,
        on_set_default_skill_selected,
        key=None,
    ):
        super().__init__(key=key)
        self.skills = list(skills)
        self.default_skill_ids = list(default_skill_ids)
        self.system_skills_folder = system_skills_folder
        self.user_skills_folder = user_skills_folder
        self.on_set_default_skill_selected = on_set_default_skill_selected

    def _folder_row(self, color_scheme, label: str, folder: Path):
        return Container(
            padding=EdgeInsets.fromLTRB(12, 10, 12, 10),
            decoration=BoxDecoration(
                borderRadius=BorderRadius.circular(8),
                border=Border.all(width=1, color=color_scheme.outlineVariant),
            ),
            child=Row(
                mainAxisSize=MainAxisSize.max,
                children=[
                    Expanded(
                        child=Column(
                            crossAxisAlignment=CrossAxisAlignment.start,
                            children=[
                                Text(
                                    label,
                                    style=TextStyle(
                                        fontSize=12,
                                        fontWeight=FontWeight.w600,
                                        color=color_scheme.onSurface,
                                    ),
                                ),
                                SizedBox(height=2),
                                Text(
                                    str(folder),
                                    maxLines=1,
                                    overflow=TextOverflow.ellipsis,
                                    style=TextStyle(
                                        fontSize=11,
                                        color=color_scheme.onSurfaceVariant,
                                    ),
                                ),
                            ],
                        )
                    ),
                    SizedBox(width=8),
                    TextButton(
                        onPressed=lambda: RockySystem.open_folder(folder),
                        child=Row(
                            mainAxisSize=MainAxisSize.min,
                            children=[
                                Icon(
                                    Icons.folder_open,
                                    size=16,
                                    color=color_scheme.onSurfaceVariant,
                                ),
                                SizedBox(width=6),
                                Text(
                                    "Open",
                                    style=TextStyle(
                                        fontSize=12,
                                        color=color_scheme.onSurfaceVariant,
                                    ),
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _skill_row(self, color_scheme, skill: Skill):
        selected = skill.id in self.default_skill_ids
        radius = BorderRadius.circular(8)
        return Material(
            color=color_scheme.surfaceContainerLowest,
            borderRadius=radius,
            child=InkWell(
                onTap=lambda: self.on_set_default_skill_selected(
                    skill.id, not selected
                ),
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
                                onChanged=(
                                    lambda value: self.on_set_default_skill_selected(
                                        skill.id,
                                        bool(value),
                                    )
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
                                )
                            ),
                        ],
                    ),
                ),
            ),
        )

    def _skill_group(self, color_scheme, title: str, source: SkillSource):
        skills = [skill for skill in self.skills if skill.source == source]
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
        return Column(
            crossAxisAlignment=CrossAxisAlignment.stretch,
            children=[
                Text(
                    "Skills",
                    style=TextStyle(
                        fontSize=18,
                        fontWeight=FontWeight.w600,
                        color=color_scheme.onSurface,
                    ),
                ),
                SizedBox(height=16),
                Row(
                    mainAxisSize=MainAxisSize.max,
                    children=[
                        Expanded(
                            child=self._folder_row(
                                color_scheme,
                                "System Skills",
                                self.system_skills_folder,
                            )
                        ),
                        SizedBox(width=12),
                        Expanded(
                            child=self._folder_row(
                                color_scheme,
                                "User Skills",
                                self.user_skills_folder,
                            )
                        ),
                    ],
                ),
                SizedBox(height=18),
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
        )
