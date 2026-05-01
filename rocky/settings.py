from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from rocky.agentic.contracts.skill import Skill
from rocky.contracts.mcp import RockyMcpServerProfile
from rocky.contracts.model import RockyModelProfile, RockyModelProviderName
from rocky.contracts.settings import (
    RockyChatsSettings,
    RockySettingsData,
    RockyThemeSettings,
)
from rocky.contracts.shell import ROCKY_LOCAL_SHELL_PROFILE_ID, RockyShellProfile
from rocky.services.skills_discovery import RockySkillsDiscovery
from rocky.system import RockySystem
from flut.flutter.foundation.change_notifier import ChangeNotifier

logger = logging.getLogger(__name__)

SETTINGS_FILENAME = "settings.json"
ROCKY_USER_FOLDER_NAME = ".rocky"
WORKSPACE_HOME_FOLDER_NAME = "workspace"
SKILLS_FOLDER_NAME = "skills"
ROCKY_RUNTIME_FOLDER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir)
)


class RockySettings(ChangeNotifier):
    _instance: Optional["RockySettings"] = None

    def __init__(self):
        super().__init__()
        self._rocky_runtime_folder = ROCKY_RUNTIME_FOLDER
        self._home_folder = os.path.abspath(os.path.expanduser("~"))
        self._rocky_user_folder = os.path.join(
            self._home_folder, ROCKY_USER_FOLDER_NAME
        )
        self._workspace_home_folder = os.path.join(
            self._rocky_user_folder, WORKSPACE_HOME_FOLDER_NAME
        )
        self._system_skills_folder = os.path.join(
            self._rocky_runtime_folder, SKILLS_FOLDER_NAME
        )
        self._user_skills_folder = os.path.join(
            self._rocky_user_folder, SKILLS_FOLDER_NAME
        )
        self._theme = RockyThemeSettings()
        self._chats = RockyChatsSettings()
        self._model_profiles: list[RockyModelProfile] = []
        self._default_model_profile_id: Optional[str] = None
        self._shell_profiles: list[RockyShellProfile] = []
        self._default_shell_profile_ids: list[str] = []
        self._mcp_server_profiles: list[RockyMcpServerProfile] = []
        self._default_mcp_server_ids: list[str] = []
        self._skills: list[Skill] = []
        self._default_skill_ids: list[str] = []
        self._load()

    @classmethod
    def load(cls) -> "RockySettings":
        if cls._instance is not None:
            raise RuntimeError("RockySettings is already loaded.")
        cls._instance = cls()
        return cls._instance

    @classmethod
    def current(cls) -> "RockySettings":
        if cls._instance is None:
            raise RuntimeError("RockySettings is not loaded yet.")
        return cls._instance

    @property
    def rocky_runtime_folder(self) -> str:
        return self._rocky_runtime_folder

    @property
    def home_folder(self) -> str:
        return self._home_folder

    @property
    def rocky_user_folder(self) -> str:
        return self._rocky_user_folder

    @property
    def workspace_home_folder(self) -> str:
        return self._workspace_home_folder

    @property
    def system_skills_folder(self) -> str:
        return self._system_skills_folder

    @property
    def user_skills_folder(self) -> str:
        return self._user_skills_folder

    @property
    def theme(self) -> RockyThemeSettings:
        return self._theme

    @property
    def chats(self) -> RockyChatsSettings:
        return self._chats

    @property
    def model_profiles(self) -> list[RockyModelProfile]:
        return list(self._model_profiles)

    @property
    def default_model_profile_id(self) -> Optional[str]:
        return self._default_model_profile_id

    @property
    def default_model_profile(self) -> Optional[RockyModelProfile]:
        for model_profile in self._model_profiles:
            if model_profile.id == self._default_model_profile_id:
                return model_profile
        return None

    @property
    def shell_profiles(self) -> list[RockyShellProfile]:
        return list(self._shell_profiles)

    @property
    def default_shell_profile_ids(self) -> list[str]:
        return list(self._default_shell_profile_ids)

    @property
    def default_shell_profiles(self) -> list[RockyShellProfile]:
        default_ids = set(self._default_shell_profile_ids)
        return [
            shell_profile
            for shell_profile in self._shell_profiles
            if shell_profile.id in default_ids
        ]

    @property
    def mcp_server_profiles(self) -> list[RockyMcpServerProfile]:
        return list(self._mcp_server_profiles)

    @property
    def default_mcp_server_ids(self) -> list[str]:
        return list(self._default_mcp_server_ids)

    @property
    def default_mcp_server_profiles(self) -> list[RockyMcpServerProfile]:
        return self.find_mcp_server_profiles(self._default_mcp_server_ids)

    @property
    def skills(self) -> list[Skill]:
        return list(self._skills)

    @property
    def default_skill_ids(self) -> list[str]:
        return list(self._default_skill_ids)

    @property
    def default_skills(self) -> list[Skill]:
        return self.find_skills(self._default_skill_ids)

    def find_model_profile(
        self, model_profile_id: Optional[str]
    ) -> Optional[RockyModelProfile]:
        if model_profile_id is None:
            return None
        for model_profile in self._model_profiles:
            if model_profile.id == model_profile_id:
                return model_profile
        return None

    def find_shell_profiles(
        self, shell_profile_ids: list[str]
    ) -> list[RockyShellProfile]:
        wanted = list(shell_profile_ids or [])
        index = {
            shell_profile.id: shell_profile for shell_profile in self._shell_profiles
        }
        result: list[RockyShellProfile] = []
        for shell_profile_id in wanted:
            shell_profile = index.get(shell_profile_id)
            if shell_profile is not None:
                result.append(shell_profile)
        return result

    def find_skills(self, skill_ids: list[str]) -> list[Skill]:
        wanted = list(skill_ids or [])
        index = {skill.id: skill for skill in self._skills}
        result: list[Skill] = []
        for skill_id in wanted:
            skill = index.get(skill_id)
            if skill is not None:
                result.append(skill)
        return result

    def find_mcp_server_profiles(
        self, mcp_server_ids: list[str]
    ) -> list[RockyMcpServerProfile]:
        wanted = list(mcp_server_ids or [])
        index = {mcp_server.id: mcp_server for mcp_server in self._mcp_server_profiles}
        result: list[RockyMcpServerProfile] = []
        for mcp_server_id in wanted:
            mcp_server = index.get(mcp_server_id)
            if mcp_server is not None:
                result.append(mcp_server)
        return result

    def is_model_profile_selectable(self, model_profile: RockyModelProfile) -> bool:
        if model_profile.provider == RockyModelProviderName.LITERTLM:
            return RockySystem.is_litert_lm_installed()
        return True

    def model_profile_ready(
        self, model_profile: Optional[RockyModelProfile]
    ) -> tuple[bool, Optional[str]]:
        if model_profile is None:
            return False, "Select a model for this chat."
        if model_profile.provider == RockyModelProviderName.LITERTLM:
            if not RockySystem.is_litert_lm_installed():
                return False, "LiteRT-LM is not installed."
            if not model_profile.name:
                return False, "Configure a LiteRT-LM model file in Settings."
            return True, None
        if model_profile.provider == RockyModelProviderName.OPENAI_COMPATIBLE:
            if not model_profile.name or not model_profile.endpoint:
                return False, "Configure a model and endpoint in Settings."
            return True, None
        if not model_profile.name or not model_profile.key:
            return False, "Configure a model in Settings."
        if (
            model_profile.provider == RockyModelProviderName.AZURE_OPENAI
            and not model_profile.endpoint
        ):
            return False, "Configure a model in Settings."
        return True, None

    def toggle_dark_mode(self) -> None:
        self._theme = self._theme.model_copy(
            update={
                "brightness": "light" if self._theme.brightness == "dark" else "dark"
            }
        )
        self._save_and_notify()

    def toggle_tint(self) -> None:
        self._theme = self._theme.model_copy(update={"tint": not self._theme.tint})
        self._save_and_notify()

    def set_theme_color(self, color: str) -> None:
        self._theme = self._theme.model_copy(update={"color": color})
        self._save_and_notify()

    def set_max_chats(self, value: Optional[int]) -> None:
        if value is not None and value <= 0:
            value = None
        if self._chats.max_chats == value:
            return
        self._chats = self._chats.model_copy(update={"max_chats": value})
        self._save_and_notify()

    def add_model_profile(self, model_profile: RockyModelProfile) -> RockyModelProfile:
        self._model_profiles = self._model_profiles + [model_profile]
        if self._default_model_profile_id is None and self.is_model_profile_selectable(
            model_profile
        ):
            self._default_model_profile_id = model_profile.id
        self._save_and_notify()
        return model_profile

    def update_model_profile(
        self, model_profile: RockyModelProfile
    ) -> RockyModelProfile:
        replaced = False
        next_profiles: list[RockyModelProfile] = []
        for existing in self._model_profiles:
            if existing.id == model_profile.id:
                next_profiles.append(model_profile)
                replaced = True
            else:
                next_profiles.append(existing)
        if not replaced:
            return model_profile
        self._model_profiles = next_profiles
        if (
            self._default_model_profile_id == model_profile.id
            and not self.is_model_profile_selectable(model_profile)
        ):
            self._default_model_profile_id = self._first_selectable_model_profile_id()
        self._save_and_notify()
        return model_profile

    def delete_model_profile(self, model_profile_id: str) -> None:
        self._model_profiles = [
            model_profile
            for model_profile in self._model_profiles
            if model_profile.id != model_profile_id
        ]
        if self._default_model_profile_id == model_profile_id:
            self._default_model_profile_id = self._first_selectable_model_profile_id()
        self._save_and_notify()

    def set_default_model_profile(self, model_profile_id: str) -> None:
        model_profile = self.find_model_profile(model_profile_id)
        if model_profile is None or not self.is_model_profile_selectable(model_profile):
            return
        if self._default_model_profile_id == model_profile_id:
            return
        self._default_model_profile_id = model_profile_id
        self._save_and_notify()

    def add_shell_profile(self, shell_profile: RockyShellProfile) -> RockyShellProfile:
        self._shell_profiles = self._shell_profiles + [shell_profile]
        self._save_and_notify()
        return shell_profile

    def update_shell_profile(
        self, shell_profile: RockyShellProfile
    ) -> RockyShellProfile:
        replaced = False
        next_profiles: list[RockyShellProfile] = []
        for existing in self._shell_profiles:
            if existing.id == shell_profile.id:
                next_profiles.append(shell_profile)
                replaced = True
            else:
                next_profiles.append(existing)
        if not replaced:
            return shell_profile
        self._shell_profiles = next_profiles
        self._save_and_notify()
        return shell_profile

    def delete_shell_profile(self, shell_profile_id: str) -> None:
        self._shell_profiles = [
            shell_profile
            for shell_profile in self._shell_profiles
            if shell_profile.id != shell_profile_id
        ]
        self._default_shell_profile_ids = [
            default_id
            for default_id in self._default_shell_profile_ids
            if default_id != shell_profile_id
        ]
        self._save_and_notify()

    def set_default_shell_profile_selected(
        self, shell_profile_id: str, selected: bool
    ) -> None:
        shell_profile = next(
            (
                candidate
                for candidate in self._shell_profiles
                if candidate.id == shell_profile_id
            ),
            None,
        )
        if shell_profile is None:
            return
        default_ids = list(self._default_shell_profile_ids)
        already_selected = shell_profile_id in default_ids
        if selected and not already_selected:
            default_ids.append(shell_profile_id)
        elif not selected and already_selected:
            default_ids = [
                default_id
                for default_id in default_ids
                if default_id != shell_profile_id
            ]
        else:
            return
        self._default_shell_profile_ids = default_ids
        self._save_and_notify()

    def set_default_skill_selected(self, skill_id: str, selected: bool) -> None:
        skill = next(
            (candidate for candidate in self._skills if candidate.id == skill_id),
            None,
        )
        if skill is None:
            return
        default_ids = list(self._default_skill_ids)
        already_selected = skill_id in default_ids
        if selected and not already_selected:
            default_ids.append(skill_id)
        elif not selected and already_selected:
            default_ids = [
                default_id for default_id in default_ids if default_id != skill_id
            ]
        else:
            return
        self._default_skill_ids = default_ids
        self._save_and_notify()

    def add_mcp_server_profile(
        self, mcp_server_profile: RockyMcpServerProfile
    ) -> RockyMcpServerProfile:
        self._mcp_server_profiles = self._mcp_server_profiles + [mcp_server_profile]
        self._save_and_notify()
        return mcp_server_profile

    def update_mcp_server_profile(
        self, mcp_server_profile: RockyMcpServerProfile
    ) -> RockyMcpServerProfile:
        replaced = False
        next_profiles: list[RockyMcpServerProfile] = []
        for existing in self._mcp_server_profiles:
            if existing.id == mcp_server_profile.id:
                next_profiles.append(mcp_server_profile)
                replaced = True
            else:
                next_profiles.append(existing)
        if not replaced:
            return mcp_server_profile
        self._mcp_server_profiles = next_profiles
        self._save_and_notify()
        return mcp_server_profile

    def delete_mcp_server_profile(self, mcp_server_id: str) -> None:
        self._mcp_server_profiles = [
            mcp_server
            for mcp_server in self._mcp_server_profiles
            if mcp_server.id != mcp_server_id
        ]
        self._default_mcp_server_ids = [
            default_id
            for default_id in self._default_mcp_server_ids
            if default_id != mcp_server_id
        ]
        self._save_and_notify()

    def set_default_mcp_server_selected(
        self, mcp_server_id: str, selected: bool
    ) -> None:
        mcp_server = next(
            (
                candidate
                for candidate in self._mcp_server_profiles
                if candidate.id == mcp_server_id
            ),
            None,
        )
        if mcp_server is None:
            return
        default_ids = list(self._default_mcp_server_ids)
        already_selected = mcp_server_id in default_ids
        if selected and not already_selected:
            default_ids.append(mcp_server_id)
        elif not selected and already_selected:
            default_ids = [
                default_id for default_id in default_ids if default_id != mcp_server_id
            ]
        else:
            return
        self._default_mcp_server_ids = default_ids
        self._save_and_notify()

    def _first_selectable_model_profile_id(self) -> Optional[str]:
        for model_profile in self._model_profiles:
            if self.is_model_profile_selectable(model_profile):
                return model_profile.id
        return None

    def _local_shell_profile(self) -> RockyShellProfile:
        return RockyShellProfile(
            id=ROCKY_LOCAL_SHELL_PROFILE_ID,
            display_name=f"This {RockySystem.os_display_name()}",
            shell_type="local",
        )

    def _ensure_local_shell_profile(self) -> None:
        self._shell_profiles = [
            self._local_shell_profile(),
            *[
                shell_profile
                for shell_profile in self._shell_profiles
                if shell_profile.id != ROCKY_LOCAL_SHELL_PROFILE_ID
            ],
        ]

    def _path(self) -> Path:
        return Path(self._rocky_user_folder) / SETTINGS_FILENAME

    def _load(self) -> None:
        Path(self._rocky_user_folder).mkdir(parents=True, exist_ok=True)
        Path(self._workspace_home_folder).mkdir(parents=True, exist_ok=True)
        Path(self._system_skills_folder).mkdir(parents=True, exist_ok=True)
        Path(self._user_skills_folder).mkdir(parents=True, exist_ok=True)
        self._skills = RockySkillsDiscovery(
            system_skills_folder=self._system_skills_folder,
            user_skills_folder=self._user_skills_folder,
        ).discover()
        self._ensure_local_shell_profile()
        path = self._path()
        if not path.exists():
            self._save()
            return
        try:
            settings_object = json.loads(path.read_text(encoding="utf-8"))
            data = RockySettingsData.model_validate(settings_object)
        except (json.JSONDecodeError, ValidationError):
            logger.exception("Failed to parse %s", path)
            data = RockySettingsData()

        default_model_profile_id = data.default_model_id
        selectable_ids = {
            model_profile.id
            for model_profile in data.models
            if self.is_model_profile_selectable(model_profile)
        }
        if default_model_profile_id not in selectable_ids:
            default_model_profile_id = None
        if default_model_profile_id is None:
            for model_profile in data.models:
                if model_profile.id in selectable_ids:
                    default_model_profile_id = model_profile.id
                    break

        self._theme = data.theme
        self._chats = data.chats
        self._model_profiles = list(data.models)
        self._default_model_profile_id = default_model_profile_id
        self._shell_profiles = list(data.shells)
        self._ensure_local_shell_profile()
        self._mcp_server_profiles = list(data.mcp_servers)
        shell_profile_ids = {shell_profile.id for shell_profile in self._shell_profiles}
        self._default_shell_profile_ids = [
            default_id
            for default_id in data.default_shell_ids
            if default_id in shell_profile_ids
        ]
        skill_ids = {skill.id for skill in self._skills}
        self._default_skill_ids = [
            default_id
            for default_id in data.default_skill_ids
            if default_id in skill_ids
        ]
        mcp_server_ids = {mcp_server.id for mcp_server in self._mcp_server_profiles}
        self._default_mcp_server_ids = [
            default_id
            for default_id in data.default_mcp_server_ids
            if default_id in mcp_server_ids
        ]

    def _save(self) -> None:
        data = RockySettingsData(
            theme=self._theme,
            chats=self._chats,
            models=list(self._model_profiles),
            default_model_id=self._default_model_profile_id,
            shells=list(self._shell_profiles),
            default_shell_ids=list(self._default_shell_profile_ids),
            default_skill_ids=list(self._default_skill_ids),
            mcp_servers=list(self._mcp_server_profiles),
            default_mcp_server_ids=list(self._default_mcp_server_ids),
        )
        self._path().write_text(data.model_dump_json(indent=2), encoding="utf-8")

    def _save_and_notify(self) -> None:
        self._save()
        self.notifyListeners()
