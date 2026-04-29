from __future__ import annotations

import logging
from pathlib import Path

from rocky.agentic.contracts.skill import Skill, SkillSource
from rocky.agentic.tools.skill_provider import SkillProvider

logger = logging.getLogger(__name__)


class RockySkillsDiscovery:
    def __init__(self, *, system_skills_folder: Path, user_skills_folder: Path):
        self._system_skills_folder = system_skills_folder
        self._user_skills_folder = user_skills_folder

    def discover(self) -> list[Skill]:
        return [
            *self._discover_folder(self._system_skills_folder, SkillSource.SYSTEM),
            *self._discover_folder(self._user_skills_folder, SkillSource.USER),
        ]

    def _discover_folder(self, folder: Path, source: SkillSource) -> list[Skill]:
        if not folder.exists():
            return []
        if not folder.is_dir():
            logger.error("Skill folder is not a directory: %s", folder)
            return []
        skill_folders = {
            child.name.casefold() for child in folder.iterdir() if child.is_dir()
        }
        skills: list[Skill] = []
        for skill_path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
            if skill_path.is_dir():
                skill = SkillProvider(
                    skill_path=str(skill_path), source=source
                ).provide()
            elif skill_path.is_file() and skill_path.suffix.lower() == ".zip":
                if skill_path.stem.casefold() in skill_folders:
                    logger.warning(
                        "Ignoring skill zip because skill folder exists: %s",
                        skill_path,
                    )
                    continue
                skill = SkillProvider(
                    skill_path=str(skill_path), source=source
                ).provide()
            else:
                continue
            if skill is not None:
                skills.append(skill)
        return skills
