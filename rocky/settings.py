from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from rocky.contracts.model import RockyModelProfile, RockyModelProviderName
from rocky.contracts.settings import (
    RockyChatsSettings,
    RockySettingsData,
    RockyThemeSettings,
)
from rocky.contracts.shell import RockyShellProfile
from rocky.system import RockySystem
from flut.flutter.foundation.change_notifier import ChangeNotifier

logger = logging.getLogger(__name__)

SETTINGS_FILENAME = "settings.json"
WORKDIR_ENV = "ROCKY_WORKDIR"
DEFAULT_WORKDIR_NAME = ".rocky"
_APP_ROOT = Path(__file__).resolve().parent.parent


class RockySettings(ChangeNotifier):
    _instance: Optional["RockySettings"] = None

    def __init__(self, work_dir: Path):
        super().__init__()
        self._work_dir = Path(work_dir)
        self._theme = RockyThemeSettings()
        self._chats = RockyChatsSettings()
        self._profiles: list[RockyModelProfile] = []
        self._selected_profile_id: Optional[str] = None
        self._shells: list[RockyShellProfile] = []
        self._selected_shell_ids: list[str] = []
        self._load()

    @classmethod
    def _resolve_work_dir(cls) -> Path:
        override = os.getenv(WORKDIR_ENV)
        if override:
            return Path(override).expanduser().resolve()
        return (_APP_ROOT / DEFAULT_WORKDIR_NAME).resolve()

    @classmethod
    def load(cls, work_dir: Optional[Path] = None) -> "RockySettings":
        if cls._instance is not None:
            raise RuntimeError("RockySettings is already loaded.")
        resolved = (
            Path(work_dir).resolve()
            if work_dir is not None
            else cls._resolve_work_dir()
        )
        resolved.mkdir(parents=True, exist_ok=True)
        cls._instance = cls(resolved)
        return cls._instance

    @classmethod
    def current(cls) -> "RockySettings":
        if cls._instance is None:
            raise RuntimeError("RockySettings is not loaded yet.")
        return cls._instance

    @property
    def work_dir(self) -> Path:
        return self._work_dir

    @property
    def theme(self) -> RockyThemeSettings:
        return self._theme

    @property
    def chats(self) -> RockyChatsSettings:
        return self._chats

    @property
    def profiles(self) -> list[RockyModelProfile]:
        return list(self._profiles)

    @property
    def selected_profile_id(self) -> Optional[str]:
        return self._selected_profile_id

    @property
    def selected_profile(self) -> Optional[RockyModelProfile]:
        for profile in self._profiles:
            if profile.id == self._selected_profile_id:
                return profile
        return None

    @property
    def shells(self) -> list[RockyShellProfile]:
        return list(self._shells)

    @property
    def selected_shell_ids(self) -> list[str]:
        return list(self._selected_shell_ids)

    @property
    def selected_shells(self) -> list[RockyShellProfile]:
        selected_ids = set(self._selected_shell_ids)
        return [shell for shell in self._shells if shell.id in selected_ids]

    def chat_ready(self) -> tuple[bool, Optional[str]]:
        profile = self.selected_profile
        if profile is None:
            return False, "Configure a model in Settings."
        if profile.provider == RockyModelProviderName.LITERTLM:
            if not RockySystem.is_litert_lm_installed():
                return False, "LiteRT-LM is not installed."
            if not profile.name:
                return False, "Configure a LiteRT-LM model file in Settings."
            return True, None
        if not profile.name or not profile.key:
            return False, "Configure a model in Settings."
        if (
            profile.provider == RockyModelProviderName.AZURE_OPENAI
            and not profile.endpoint
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

    def add_profile(self, profile: RockyModelProfile) -> RockyModelProfile:
        self._profiles = self._profiles + [profile]
        if self._selected_profile_id is None and self._is_selectable(profile):
            self._selected_profile_id = profile.id
        self._save_and_notify()
        return profile

    def update_profile(self, profile: RockyModelProfile) -> RockyModelProfile:
        replaced = False
        new_profiles: list[RockyModelProfile] = []
        for existing in self._profiles:
            if existing.id == profile.id:
                new_profiles.append(profile)
                replaced = True
            else:
                new_profiles.append(existing)
        if not replaced:
            return profile
        self._profiles = new_profiles
        if self._selected_profile_id == profile.id and not self._is_selectable(profile):
            self._selected_profile_id = self._first_selectable_id()
        self._save_and_notify()
        return profile

    def delete_profile(self, profile_id: str) -> None:
        self._profiles = [p for p in self._profiles if p.id != profile_id]
        if self._selected_profile_id == profile_id:
            self._selected_profile_id = self._first_selectable_id()
        self._save_and_notify()

    def select_profile(self, profile_id: str) -> None:
        profile = next((p for p in self._profiles if p.id == profile_id), None)
        if profile is None or not self._is_selectable(profile):
            return
        if self._selected_profile_id == profile_id:
            return
        self._selected_profile_id = profile_id
        self._save_and_notify()

    def add_shell(self, shell: RockyShellProfile) -> RockyShellProfile:
        self._shells = self._shells + [shell]
        if not self._selected_shell_ids:
            self._selected_shell_ids = [shell.id]
        self._save_and_notify()
        return shell

    def update_shell(self, shell: RockyShellProfile) -> RockyShellProfile:
        replaced = False
        new_shells: list[RockyShellProfile] = []
        for existing in self._shells:
            if existing.id == shell.id:
                new_shells.append(shell)
                replaced = True
            else:
                new_shells.append(existing)
        if not replaced:
            return shell
        self._shells = new_shells
        self._save_and_notify()
        return shell

    def delete_shell(self, shell_id: str) -> None:
        self._shells = [shell for shell in self._shells if shell.id != shell_id]
        self._selected_shell_ids = [
            selected_id
            for selected_id in self._selected_shell_ids
            if selected_id != shell_id
        ]
        self._save_and_notify()

    def set_shell_selected(self, shell_id: str, selected: bool) -> None:
        shell = next((item for item in self._shells if item.id == shell_id), None)
        if shell is None:
            return
        selected_ids = list(self._selected_shell_ids)
        already_selected = shell_id in selected_ids
        if selected and not already_selected:
            selected_ids.append(shell_id)
        elif not selected and already_selected:
            selected_ids = [
                selected_id for selected_id in selected_ids if selected_id != shell_id
            ]
        else:
            return
        self._selected_shell_ids = selected_ids
        self._save_and_notify()

    @staticmethod
    def _is_selectable(profile: RockyModelProfile) -> bool:
        if profile.provider == RockyModelProviderName.LITERTLM:
            return RockySystem.is_litert_lm_installed()
        return True

    def _first_selectable_id(self) -> Optional[str]:
        for profile in self._profiles:
            if self._is_selectable(profile):
                return profile.id
        return None

    def _path(self) -> Path:
        return self._work_dir / SETTINGS_FILENAME

    def _load(self) -> None:
        self._work_dir.mkdir(parents=True, exist_ok=True)
        path = self._path()
        if not path.exists():
            self._save()
            return
        try:
            settings_object = json.loads(path.read_text(encoding="utf-8"))
            data = RockySettingsData.model_validate(settings_object, extra="forbid")
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Failed to parse %s: %s", path, exc)
            data = RockySettingsData()

        selected = data.selected_model_id
        selectable_ids = {
            profile.id for profile in data.models if self._is_selectable(profile)
        }
        if selected not in selectable_ids:
            selected = None
        if selected is None:
            for profile in data.models:
                if profile.id in selectable_ids:
                    selected = profile.id
                    break

        self._theme = data.theme
        self._chats = data.chats
        self._profiles = list(data.models)
        self._selected_profile_id = selected
        self._shells = list(data.shells)
        shell_ids = {shell.id for shell in self._shells}
        self._selected_shell_ids = [
            selected_id
            for selected_id in data.selected_shell_ids
            if selected_id in shell_ids
        ]

    def _save(self) -> None:
        data = RockySettingsData(
            theme=self._theme,
            chats=self._chats,
            models=list(self._profiles),
            selected_model_id=self._selected_profile_id,
            shells=list(self._shells),
            selected_shell_ids=list(self._selected_shell_ids),
        )
        self._path().write_text(data.model_dump_json(indent=2), encoding="utf-8")

    def _save_and_notify(self) -> None:
        self._save()
        self.notifyListeners()
