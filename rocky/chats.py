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

    def save_chat(self, data: RockyChatData) -> None:
        path = self._chats_dir / f"{data.metadata.id}.json"
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
        self._install_draft(RockyChat())
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
        if self._draft is not None and not self._draft.has_messages:
            if self._current is not self._draft:
                self._current = self._draft
                self.notifyListeners()
            return
        self._start_draft()

    def select(self, chat_id: str) -> None:
        for chat in self._chats:
            if chat.id == chat_id:
                self._current = chat
                self.notifyListeners()
                return

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

    def _start_draft(self) -> None:
        if self._draft is not None:
            self._draft.removeListener(self._notify)
            self._draft = None
        self._install_draft(RockyChat())
        self.notifyListeners()

    def _install_draft(self, chat: RockyChat) -> None:
        chat.set_agent_provider(self._provision_agent, self._derive_agent_config)
        chat.set_on_message_complete(self._on_chat_message_complete)
        chat.addListener(self._notify)
        self._draft = chat
        self._current = chat

    def _provision_agent(self) -> RockyAgent:
        agent = RockyAgent()
        agent.configure(self._derive_agent_config())
        return agent

    def _derive_agent_config(self) -> Optional[RockyAgentConfig]:
        ready, _ = self._settings.chat_ready()
        if not ready:
            return None
        profile = self._settings.selected_profile
        if profile is None:
            return None
        return RockyAgentConfig(model_profile=profile)

    def _apply_settings(self) -> None:
        self._enforce_max_chats()
        self.notifyListeners()

    def _notify(self) -> None:
        self.notifyListeners()

    def _on_chat_message_complete(self, chat: RockyChat) -> None:
        if self._draft is chat and chat.has_messages:
            self._chats.insert(0, chat)
            self._draft = None
        if chat in self._chats:
            self._persister.save_chat(chat.to_data())
            self._enforce_max_chats()
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
                    metadata = body.metadata
                    messages = list(body.messages)
            chat = RockyChat(metadata=metadata, messages=messages)
            chat.set_agent_provider(self._provision_agent, self._derive_agent_config)
            chat.set_on_message_complete(self._on_chat_message_complete)
            chat.addListener(self._notify)
            self._chats.append(chat)
        self._chats.sort(key=lambda chat: chat.metadata.updated_at, reverse=True)
