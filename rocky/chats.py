from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

from pydantic import ValidationError

from rocky.agent import RockyAgent
from rocky.chat import RockyChat
from rocky.contracts.agent import RockyAgentConfig
from rocky.contracts.chat import RockyChatData, RockyChatMessage, RockyChatMetadata
from flut.flutter.foundation.change_notifier import ChangeNotifier
from rocky.models.capabilities import RockyModelCapabilities
from rocky.settings import RockySettings

logger = logging.getLogger(__name__)

CHATS_METADATA_FILENAME = "chats.json"
CHATS_DIRNAME = "chats"


class _ChatPersister:
    def __init__(self, work_dir: Path):
        self._metadata_path = work_dir / CHATS_METADATA_FILENAME
        self._chats_dir = work_dir / CHATS_DIRNAME
        self._chats_dir.mkdir(parents=True, exist_ok=True)
        self._queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="rocky-chats-persister"
        )
        self._thread.start()

    def save_chat(self, chat_id: str, data: RockyChatData) -> None:
        path = self._chats_dir / f"{chat_id}.json"
        payload = data.model_dump_json(indent=2)
        self._queue.put(lambda: path.write_text(payload, encoding="utf-8"))

    def save_all_metadata(self, items: list[RockyChatMetadata]) -> None:
        payload = json.dumps([item.model_dump() for item in items], indent=2)
        self._queue.put(
            lambda: self._metadata_path.write_text(payload, encoding="utf-8")
        )

    def delete_chat(self, chat_id: str) -> None:
        path = self._chats_dir / f"{chat_id}.json"
        self._queue.put(lambda: path.unlink(missing_ok=True))

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            try:
                task()
            except OSError as exc:
                logger.warning("Chat persistence task failed: %s", exc)


class RockyChats(ChangeNotifier):
    def __init__(self, settings: RockySettings):
        super().__init__()
        self._settings = settings
        self._persister = _ChatPersister(settings.work_dir)
        self._chats: list[RockyChat] = []
        self._draft: Optional[RockyChat] = None
        self._current: Optional[RockyChat] = None
        self._load()
        self._install_draft(self._build_draft())
        self._settings.addListener(self._apply_settings)

    @property
    def saved(self) -> list[RockyChat]:
        return sorted(
            self._chats, key=lambda chat: chat.metadata.updated_at, reverse=True
        )

    @property
    def current(self) -> RockyChat:
        if self._current is None:
            raise RuntimeError("RockyChats has no current chat.")
        return self._current

    def new_chat(self) -> None:
        if self._current is self._draft:
            return
        self._start_draft()

    def select(self, chat_id: str) -> None:
        target = next((chat for chat in self._chats if chat.id == chat_id), None)
        if target is None:
            return
        if self._current is self._draft:
            self._discard_draft()
        self._current = target
        self.notifyListeners()

    def delete(self, chat_id: str) -> None:
        target = next((chat for chat in self._chats if chat.id == chat_id), None)
        if target is None:
            return
        self._chats = [chat for chat in self._chats if chat.id != chat_id]
        target.removeListener(self._notify)
        self._persister.delete_chat(chat_id)
        self._persister.save_all_metadata([chat.metadata for chat in self._chats])
        if self._current is target:
            self._start_draft()
        else:
            self.notifyListeners()

    def model_profile_for(self, chat: RockyChat):
        if chat.selected_model_profile_id is None:
            return self._settings.default_model_profile
        return self._settings.find_model_profile(chat.selected_model_profile_id)

    def shell_profiles_for(self, chat: RockyChat):
        ids = chat.selected_shell_profile_ids
        if ids is None:
            ids = self._settings.default_shell_profile_ids
        return self._settings.find_shell_profiles(ids)

    def shell_profile_ids_for(self, chat: RockyChat) -> list[str]:
        return [shell_profile.id for shell_profile in self.shell_profiles_for(chat)]

    def model_profile_id_for(self, chat: RockyChat) -> Optional[str]:
        model_profile = self.model_profile_for(chat)
        return model_profile.id if model_profile is not None else None

    def toggle_shell_profile(
        self, chat: RockyChat, shell_profile_id: str, selected: bool
    ) -> None:
        ids = list(self.shell_profile_ids_for(chat))
        already_selected = shell_profile_id in ids
        if selected and not already_selected:
            ids.append(shell_profile_id)
        elif not selected and already_selected:
            ids = [item for item in ids if item != shell_profile_id]
        else:
            return
        chat.set_shell_profile_ids(ids)

    def chat_ready(self, chat: RockyChat) -> tuple[bool, Optional[str]]:
        return self._settings.model_profile_ready(self.model_profile_for(chat))

    def _start_draft(self) -> None:
        self._discard_draft()
        self._install_draft(self._build_draft())
        self.notifyListeners()

    def _discard_draft(self) -> None:
        if self._draft is None:
            return
        self._draft.removeListener(self._notify)
        self._draft = None

    def _build_draft(self) -> RockyChat:
        return RockyChat()

    def _install_draft(self, chat: RockyChat) -> None:
        self._wire_chat(chat)
        self._draft = chat
        self._current = chat

    def _wire_chat(self, chat: RockyChat) -> None:
        chat.set_agent_provider(
            lambda c=chat: self._provision_agent(c),
            lambda c=chat: self._derive_agent_config(c),
        )
        chat.set_on_user_send(self._on_chat_user_send)
        chat.set_on_message_complete(self._on_chat_message_complete)
        chat.set_on_persist(self._on_chat_persist)
        chat.addListener(self._notify)

    def _provision_agent(self, chat: RockyChat) -> RockyAgent:
        agent = RockyAgent()
        agent.configure(self._derive_agent_config(chat))
        return agent

    def _commit_selections(self, chat: RockyChat) -> None:
        if chat.selected_model_profile_id is None:
            chat.set_selected_model_profile(self.model_profile_id_for(chat))
        if chat.selected_shell_profile_ids is None:
            chat.set_shell_profile_ids(self.shell_profile_ids_for(chat))

    def _derive_agent_config(self, chat: RockyChat) -> Optional[RockyAgentConfig]:
        ready, _ = self.chat_ready(chat)
        if not ready:
            return None
        model_profile = self.model_profile_for(chat)
        if model_profile is None:
            return None
        if RockyModelCapabilities.supports_function(model_profile):
            shell_profiles = self.shell_profiles_for(chat)
        else:
            shell_profiles = []
        return RockyAgentConfig(
            model_profile=model_profile,
            shell_profiles=shell_profiles,
        )

    def _apply_settings(self) -> None:
        self._enforce_max_chats()
        for chat in self._all_chats():
            chat.reconfigure_agent()
        self.notifyListeners()

    def _all_chats(self):
        seen = set()
        result = []
        for chat in self._chats:
            if id(chat) in seen:
                continue
            seen.add(id(chat))
            result.append(chat)
        if self._draft is not None and id(self._draft) not in seen:
            result.append(self._draft)
        return result

    def _notify(self) -> None:
        self.notifyListeners()

    def _on_chat_persist(self, chat: RockyChat) -> None:
        if chat in self._chats:
            self._persister.save_all_metadata([c.metadata for c in self._chats])

    def _on_chat_user_send(self, chat: RockyChat) -> None:
        if self._draft is chat:
            self._commit_selections(chat)
            self._chats.insert(0, chat)
            self._draft = None
        if chat in self._chats:
            self._persister.save_chat(chat.id, chat.to_data())
            self._enforce_max_chats()
            self._persister.save_all_metadata([c.metadata for c in self._chats])
        self.notifyListeners()

    def _on_chat_message_complete(self, chat: RockyChat) -> None:
        if chat in self._chats:
            self._persister.save_chat(chat.id, chat.to_data())
            self._persister.save_all_metadata([c.metadata for c in self._chats])
        self.notifyListeners()

    def _enforce_max_chats(self) -> None:
        limit = self._settings.chats.max_chats
        if limit is None or limit <= 0:
            return
        if len(self._chats) <= limit:
            return
        ordered = sorted(
            self._chats, key=lambda chat: chat.metadata.updated_at, reverse=True
        )
        keep = ordered[:limit]
        evicted = ordered[limit:]
        for chat in evicted:
            chat.removeListener(self._notify)
            self._persister.delete_chat(chat.id)
            if self._current is chat:
                self._current = None
        self._chats = [chat for chat in self._chats if chat in keep]
        self._persister.save_all_metadata([chat.metadata for chat in self._chats])
        if self._current is None:
            self._start_draft()

    def _load(self) -> None:
        metadata_path = self._settings.work_dir / CHATS_METADATA_FILENAME
        chats_dir = self._settings.work_dir / CHATS_DIRNAME
        if not metadata_path.exists():
            return
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read %s: %s", metadata_path, exc)
            return
        for item in raw or []:
            try:
                metadata = RockyChatMetadata.model_validate(item)
            except ValidationError as exc:
                logger.warning("Skipping invalid chat metadata %r: %s", item, exc)
                continue
            messages: list[RockyChatMessage] = []
            data_path = chats_dir / f"{metadata.id}.json"
            if data_path.exists():
                try:
                    body = RockyChatData.model_validate_json(
                        data_path.read_text(encoding="utf-8")
                    )
                except (OSError, ValidationError) as exc:
                    logger.warning("Failed to load %s: %s", data_path, exc)
                else:
                    messages = list(body.messages)
            chat = RockyChat(metadata=metadata, messages=messages)
            self._wire_chat(chat)
            self._chats.append(chat)
        self._chats.sort(key=lambda chat: chat.metadata.updated_at, reverse=True)
