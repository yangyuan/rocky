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
    RockyAgentStreamEventKind,
)
from rocky.contracts.chat import (
    DEFAULT_CHAT_TITLE,
    RockyAttachment,
    RockyChatData,
    RockyChatMessage,
    RockyChatMetadata,
    RockyToolCall,
)
from rocky.system import RockySystem
from flut.flutter.foundation.change_notifier import ChangeNotifier

logger = logging.getLogger(__name__)

_MAX_TITLE_LENGTH = 40


class _RockyStreamNotifier(ChangeNotifier):
    pass


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
        self._agent: Optional[RockyAgent] = None
        self._agent_provider: Optional[Callable[[], RockyAgent]] = None
        self._agent_config_provider: Optional[
            Callable[[], Optional[RockyAgentConfig]]
        ] = None
        self._on_message_complete: Callable[["RockyChat"], None] = lambda _chat: None
        self._on_user_send: Callable[["RockyChat"], None] = lambda _chat: None
        self._on_persist: Callable[["RockyChat"], None] = lambda _chat: None
        self._stream_notifier = _RockyStreamNotifier()

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
    def agent(self) -> Optional[RockyAgent]:
        return self._agent

    @property
    def has_messages(self) -> bool:
        return any(not m.streaming for m in self._messages)

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
            agent.set_history(
                [
                    message
                    for message in self._messages
                    if message.role in ("user", "assistant", "system", "developer")
                    and not message.streaming
                ]
            )

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
        attachments: Optional[list[RockyAttachment]] = None,
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
        self._messages.append(
            RockyChatMessage(
                role="user",
                content=text,
                attachments=attachments,
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
            lambda _: asyncio.create_task(self._stream_reply(text, attachments))
        )
        return True

    def to_data(self) -> RockyChatData:
        return RockyChatData(
            messages=[
                RockyChatMessage(
                    role=message.role,
                    content=message.content,
                    attachments=list(message.attachments or []),
                    tool_calls=list(message.tool_calls or []),
                )
                for message in self._messages
                if not message.streaming
            ],
        )

    async def _stream_reply(
        self,
        user_text: str,
        attachments: list[RockyAttachment],
    ) -> None:
        cancelled = False
        try:
            async for event in self._agent.stream_reply(user_text, attachments):
                if RockySystem.is_shutting_down():
                    return
                if event.type == RockyAgentStreamEventKind.TEXT_DELTA:
                    last = self._ensure_streaming_reply()
                    last.content = (last.content or "") + event.delta
                    self._stream_notifier.notifyListeners()
                elif event.type == RockyAgentStreamEventKind.MESSAGE_BOUNDARY:
                    self._finish_streaming_reply(remove_empty=True)
                elif event.type == RockyAgentStreamEventKind.DEVELOPER_MESSAGE:
                    self._append_developer_message(event.message)
                elif event.type == RockyAgentStreamEventKind.TOOL_STARTED:
                    self._finish_streaming_reply(remove_empty=True)
                    self._append_tool_call(event.tool)
                elif event.type == RockyAgentStreamEventKind.TOOL_FINISHED:
                    self._update_tool_result(event.tool)
            self._finish_streaming_reply(remove_empty=True)
            self._finish_tool_message()
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
            self._finish_streaming_reply(remove_empty=True)
            self._finish_tool_message()
            logger.warning("Chat stream failed: %s", exc)
        finally:
            if not cancelled and not RockySystem.is_shutting_down():
                self._metadata = self._metadata.model_copy(
                    update={"updated_at": time.time()}
                )
                self.notifyListeners()
                self._on_message_complete(self)
                self._maybe_refresh_title()

    def _ensure_streaming_reply(self) -> RockyChatMessage:
        if (
            self._messages
            and self._messages[-1].role == "assistant"
            and self._messages[-1].streaming
        ):
            return self._messages[-1]
        message = RockyChatMessage(
            role="assistant",
            content="",
            streaming=True,
        )
        self._messages.append(message)
        self.notifyListeners()
        return message

    def _append_developer_message(self, message: RockyChatMessage | None) -> None:
        if message is None or message.role != "developer":
            return
        developer_message = message.model_copy(update={"streaming": False})
        insert_index = len(self._messages)
        if self._messages and self._messages[-1].role == "user":
            insert_index -= 1
        self._messages.insert(insert_index, developer_message)
        self.notifyListeners()

    def _ensure_tool_message(self) -> RockyChatMessage:
        if self._messages and self._messages[-1].role == "tool":
            self._messages[-1].streaming = True
            return self._messages[-1]
        message = RockyChatMessage(role="tool", streaming=True)
        self._messages.append(message)
        return message

    def _append_tool_call(self, tool: RockyToolCall | None) -> None:
        if tool is None:
            return
        message = self._ensure_tool_message()
        message.tool_calls.append(tool)
        self.notifyListeners()
        self._stream_notifier.notifyListeners()

    def _update_tool_result(self, tool: RockyToolCall | None) -> None:
        if tool is None:
            return
        message = self._ensure_tool_message()
        target: RockyToolCall | None = None
        if tool.id:
            for entry in reversed(message.tool_calls):
                if entry.id == tool.id:
                    target = entry
                    break
        if target is None:
            for entry in reversed(message.tool_calls):
                if not entry.completed:
                    target = entry
                    break
        if target is None:
            target = RockyToolCall(id=tool.id)
            message.tool_calls.append(target)
        target.output = tool.output
        target.completed = True
        if all(entry.completed for entry in message.tool_calls):
            message.streaming = False
        self.notifyListeners()
        self._stream_notifier.notifyListeners()

    def _finish_tool_message(self) -> None:
        if not self._messages or self._messages[-1].role != "tool":
            return
        message = self._messages[-1]
        if not message.tool_calls:
            self._messages.pop()
        else:
            for entry in message.tool_calls:
                entry.completed = True
            message.streaming = False
        self.notifyListeners()
        return message

    def _finish_streaming_reply(self, *, remove_empty: bool) -> None:
        if (
            not self._messages
            or self._messages[-1].role != "assistant"
            or not self._messages[-1].streaming
        ):
            return
        if remove_empty and not (self._messages[-1].content or "").strip():
            self._messages.pop()
        else:
            self._messages[-1].streaming = False
        self.notifyListeners()

    def _maybe_refresh_title(self) -> None:
        if self._agent is None:
            return
        if self._metadata.custom_title:
            return
        completed = sum(
            1
            for message in self._messages
            if message.role == "assistant" and not message.streaming
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
