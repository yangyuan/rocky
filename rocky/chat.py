from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Callable, Optional

from flut.flutter.scheduler import SchedulerBinding

from rocky.agent import RockyAgent
from rocky.contracts.agent import (
    RockyAgentConfig,
    RockyAgentStatus,
    RockyChatChunkEvent,
)
from rocky.contracts.chat import (
    DEFAULT_CHAT_TITLE,
    RockyChatContent,
    RockyChatData,
    RockyChatFileContentPart,
    RockyChatMessage,
    RockyChatMetadata,
)
from rocky.services.attachments import RockyAttachments
from rocky.system import RockySystem
from flut.flutter.foundation.change_notifier import ChangeNotifier

logger = logging.getLogger(__name__)

_MAX_TITLE_LENGTH = 40


class RockyChat(ChangeNotifier):
    def __init__(
        self,
        *,
        metadata: Optional[RockyChatMetadata] = None,
        messages: Optional[list[RockyChatMessage]] = None,
    ):
        super().__init__()
        self._metadata = metadata or RockyChatMetadata()
        self._messages: list[RockyChatMessage] = list(messages or [])
        self._streaming_text: Optional[str] = None
        self._agent: Optional[RockyAgent] = None
        self._agent_provider: Optional[Callable[[], RockyAgent]] = None
        self._agent_config_provider: Optional[
            Callable[[], Optional[RockyAgentConfig]]
        ] = None
        self._on_message_complete: Callable[["RockyChat"], None] = lambda _chat: None
        self._on_user_send: Callable[["RockyChat"], None] = lambda _chat: None
        self._on_persist: Callable[["RockyChat"], None] = lambda _chat: None
        self._stream_notifier = ChangeNotifier()

    @property
    def id(self) -> str:
        return self._metadata.id

    @property
    def metadata(self) -> RockyChatMetadata:
        return self._metadata

    @property
    def title(self) -> str:
        return self._metadata.title

    @property
    def messages(self) -> list[RockyChatMessage]:
        return self._messages

    @property
    def busy(self) -> bool:
        if self._agent is None:
            return False
        return self._agent.busy

    @property
    def streaming_text(self) -> Optional[str]:
        return self._streaming_text

    @property
    def stream_notifier(self) -> ChangeNotifier:
        return self._stream_notifier

    @property
    def status(self) -> RockyAgentStatus:
        if self._agent is None:
            return RockyAgentStatus.UNCONFIGURED
        return self._agent.status

    @property
    def can_send(self) -> bool:
        if self._agent is not None:
            return self._agent.status != RockyAgentStatus.UNCONFIGURED
        return self._agent_provider is not None

    def set_agent_provider(
        self,
        provider: Callable[[], RockyAgent],
        config_provider: Callable[[], Optional[RockyAgentConfig]],
    ) -> None:
        self._agent_provider = provider
        self._agent_config_provider = config_provider

    def reconfigure_agent(self) -> None:
        if self._agent is None or self._agent_config_provider is None:
            return
        self._agent.configure(self._agent_config_provider())

    def _attach_agent(self, agent: RockyAgent) -> None:
        self._agent = agent
        agent.addListener(self.notifyListeners)
        if self._messages:
            agent.set_history(list(self._messages))

    def set_on_message_complete(self, callback: Callable[["RockyChat"], None]) -> None:
        self._on_message_complete = callback

    def set_on_user_send(self, callback: Callable[["RockyChat"], None]) -> None:
        self._on_user_send = callback

    def set_on_persist(self, callback: Callable[["RockyChat"], None]) -> None:
        self._on_persist = callback

    @property
    def model_profile_id(self) -> Optional[str]:
        return self._metadata.model_id

    @property
    def shell_profile_ids(self) -> Optional[list[str]]:
        ids = self._metadata.shell_ids
        return list(ids) if ids is not None else None

    @property
    def skill_ids(self) -> Optional[list[str]]:
        ids = self._metadata.skill_ids
        return list(ids) if ids is not None else None

    @property
    def mcp_server_ids(self) -> Optional[list[str]]:
        ids = self._metadata.mcp_server_ids
        return list(ids) if ids is not None else None

    @property
    def workspace_folder(self) -> Optional[str]:
        return self._metadata.workspace_folder

    def set_model_profile(self, model_profile_id: Optional[str]) -> None:
        if self._metadata.model_id == model_profile_id:
            return
        self._metadata = self._metadata.model_copy(
            update={"model_id": model_profile_id}
        )
        self.reconfigure_agent()
        self.notifyListeners()
        self._on_persist(self)

    def set_shell_profile_ids(self, shell_profile_ids: list[str]) -> None:
        new_ids = list(shell_profile_ids)
        if self._metadata.shell_ids == new_ids:
            return
        self._metadata = self._metadata.model_copy(update={"shell_ids": new_ids})
        self.reconfigure_agent()
        self.notifyListeners()
        self._on_persist(self)

    def set_skill_ids(self, skill_ids: list[str]) -> None:
        new_ids = list(skill_ids)
        if self._metadata.skill_ids == new_ids:
            return
        self._metadata = self._metadata.model_copy(update={"skill_ids": new_ids})
        self.reconfigure_agent()
        self.notifyListeners()
        self._on_persist(self)

    def set_mcp_server_ids(self, mcp_server_ids: list[str]) -> None:
        new_ids = list(mcp_server_ids)
        if self._metadata.mcp_server_ids == new_ids:
            return
        self._metadata = self._metadata.model_copy(update={"mcp_server_ids": new_ids})
        self.reconfigure_agent()
        self.notifyListeners()
        self._on_persist(self)

    def set_workspace_folder(self, workspace_folder: str) -> None:
        value = os.path.abspath(os.path.expanduser(workspace_folder))
        if self._metadata.workspace_folder == value:
            return
        self._metadata = self._metadata.model_copy(update={"workspace_folder": value})
        self.notifyListeners()
        self._on_persist(self)

    def set_title(self, title: str) -> None:
        cleaned = " ".join(title.strip().split())
        if not cleaned:
            return
        if len(cleaned) > _MAX_TITLE_LENGTH:
            cleaned = cleaned[:_MAX_TITLE_LENGTH].rstrip() + "\u2026"
        if cleaned == self._metadata.title and self._metadata.custom_title:
            return
        self._metadata = self._metadata.model_copy(
            update={
                "title": cleaned,
                "custom_title": True,
            }
        )
        self.notifyListeners()
        self._on_message_complete(self)

    def send_message(
        self,
        text: str,
        attachments: Optional[list[RockyChatFileContentPart]] = None,
    ) -> bool:
        attachments = list(attachments or [])
        if not text.strip() and not attachments:
            return False
        if self.busy:
            return False
        if self._agent is None:
            if self._agent_provider is None:
                logger.warning("Ignoring send: no agent provider configured.")
                return False
            self._attach_agent(self._agent_provider())
        elif self._agent_config_provider is not None:
            self._agent.configure(self._agent_config_provider())
        if self._agent.status == RockyAgentStatus.UNCONFIGURED:
            logger.warning("Ignoring send: agent is not configured.")
            return False
        user_content = RockyAttachments.message_content(text, attachments)
        self._messages.append(
            RockyChatMessage(
                role="user",
                content=user_content,
            )
        )
        self._metadata = self._metadata.model_copy(update={"updated_at": time.time()})
        if (
            self._metadata.title == DEFAULT_CHAT_TITLE
            or not self._metadata.title.strip()
        ):
            title_seed = text.strip() or (
                attachments[0].filename if attachments else ""
            )
            self._metadata = self._metadata.model_copy(
                update={"title": self._derive_title(title_seed)}
            )
        self.notifyListeners()
        self._on_user_send(self)
        SchedulerBinding.instance.addPostFrameCallback(
            lambda _: asyncio.create_task(self._stream_reply(user_content))
        )
        return True

    def to_data(self) -> RockyChatData:
        return RockyChatData(
            messages=[message.model_copy(deep=True) for message in self._messages],
        )

    async def _stream_reply(
        self,
        user_content: RockyChatContent,
    ) -> None:
        cancelled = False
        try:
            async for item in self._agent.stream_reply(user_content):
                if RockySystem.is_shutting_down():
                    return
                if isinstance(item, RockyChatChunkEvent):
                    if not item.delta:
                        continue
                    self._append_streaming_text(item.delta)
                    self._stream_notifier.notifyListeners()
                elif isinstance(item, RockyChatMessage):
                    self._append_completed_message(item)
            self._finish_streaming_text(remove_empty=True)
        except asyncio.CancelledError:
            cancelled = True
            raise
        except RuntimeError as exc:
            RockySystem.request_shutdown()
            logger.debug("Chat stream stopped during shutdown: %s", exc)
            return
        except Exception as exc:
            if RockySystem.is_shutting_down():
                return
            self._finish_streaming_text(remove_empty=True)
            logger.warning("Chat stream failed: %s", exc)
        finally:
            if not cancelled and not RockySystem.is_shutting_down():
                if self._agent is not None:
                    self._agent.set_history(list(self._messages))
                self._metadata = self._metadata.model_copy(
                    update={"updated_at": time.time()}
                )
                self.notifyListeners()
                self._on_message_complete(self)
                self._maybe_refresh_title()

    def _append_streaming_text(self, delta: str) -> None:
        self._streaming_text = (self._streaming_text or "") + delta
        self.notifyListeners()

    def _append_completed_message(self, message: RockyChatMessage) -> None:
        if message.role == "developer":
            self._append_developer_message(message)
            return
        if message.role == "assistant" and not message.tool_calls:
            if self._complete_streaming_text(message):
                self._on_persist(self)
                return
        self._finish_streaming_text(remove_empty=True)
        self._messages.append(message.model_copy(deep=True))
        self.notifyListeners()
        self._stream_notifier.notifyListeners()
        self._on_persist(self)

    def _append_developer_message(self, message: RockyChatMessage) -> None:
        developer_message = message.model_copy(deep=True)
        insert_index = len(self._messages)
        if self._messages and self._messages[-1].role == "user":
            insert_index -= 1
        self._messages.insert(insert_index, developer_message)
        self.notifyListeners()
        self._on_persist(self)

    def _complete_streaming_text(self, message: RockyChatMessage) -> bool:
        if self._streaming_text is None:
            return False
        self._streaming_text = None
        self._messages.append(message.model_copy(deep=True))
        self.notifyListeners()
        self._stream_notifier.notifyListeners()
        return True

    def _finish_streaming_text(self, *, remove_empty: bool) -> None:
        if self._streaming_text is None:
            return
        if remove_empty and not self._streaming_text.strip():
            self._streaming_text = None
        else:
            self._messages.append(
                RockyChatMessage(role="assistant", content=self._streaming_text)
            )
            self._streaming_text = None
        self.notifyListeners()

    def _maybe_refresh_title(self) -> None:
        if self._agent is None:
            return
        if self._metadata.custom_title:
            return
        completed = sum(
            1
            for message in self._messages
            if message.role == "assistant" and not message.tool_calls
        )
        if completed < 1:
            return
        next_power = completed + 1
        if next_power & (next_power - 1) != 0:
            return
        asyncio.create_task(self._refresh_title())

    async def _refresh_title(self) -> None:
        agent = self._agent
        if agent is None:
            return
        try:
            title = await agent.summarize_title(self._messages)
        except Exception:
            return
        title = title.strip().strip('"').strip("'").rstrip(".")
        if not title:
            return
        if len(title) > _MAX_TITLE_LENGTH:
            title = title[:_MAX_TITLE_LENGTH].rstrip() + "\u2026"
        if title == self._metadata.title:
            return
        self._metadata = self._metadata.model_copy(
            update={"title": title, "updated_at": time.time()}
        )
        self.notifyListeners()
        self._on_message_complete(self)

    @staticmethod
    def _derive_title(text: str) -> str:
        compact = " ".join(text.strip().split())
        if not compact:
            return DEFAULT_CHAT_TITLE
        if len(compact) <= _MAX_TITLE_LENGTH:
            return compact
        return compact[:_MAX_TITLE_LENGTH].rstrip() + "\u2026"
