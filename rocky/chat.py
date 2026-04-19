from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional

from flut.flutter.scheduler import SchedulerBinding

from rocky.agent import RockyAgent
from rocky.contracts.agent import RockyAgentConfig, RockyAgentStatus
from rocky.contracts.chat import (
    DEFAULT_CHAT_TITLE,
    RockyAttachment,
    RockyChatData,
    RockyChatMessage,
    RockyChatMetadata,
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

    def _attach_agent(self, agent: RockyAgent) -> None:
        self._agent = agent
        agent.addListener(self.notifyListeners)
        if self._messages:
            agent.set_history(
                [
                    message
                    for message in self._messages
                    if message.role in ("user", "assistant") and not message.streaming
                ]
            )

    def set_on_message_complete(self, callback: Callable[["RockyChat"], None]) -> None:
        self._on_message_complete = callback

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
            RockyChatMessage(role="user", content=text, attachments=attachments)
        )
        self._messages.append(
            RockyChatMessage(role="assistant", content="", streaming=True)
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
        SchedulerBinding.instance.addPostFrameCallback(
            lambda _: asyncio.create_task(self._stream_reply(text, attachments))
        )
        return True

    def to_data(self) -> RockyChatData:
        return RockyChatData(
            metadata=self._metadata,
            messages=[
                RockyChatMessage(
                    role=message.role,
                    content=message.content,
                    attachments=list(message.attachments or []),
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
            async for delta in self._agent.stream_reply(user_text, attachments):
                if RockySystem.is_shutting_down():
                    return
                last = self._messages[-1]
                last.content = (last.content or "") + delta
                self._stream_notifier.notifyListeners()
            self._messages[-1].streaming = False
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
            self._messages[-1].streaming = False
            if not self._messages[-1].content:
                self._messages.pop()
            logger.warning("Chat stream failed: %s", exc)
        finally:
            if not cancelled and not RockySystem.is_shutting_down():
                self._metadata = self._metadata.model_copy(
                    update={"updated_at": time.time()}
                )
                self.notifyListeners()
                self._on_message_complete(self)
                self._maybe_refresh_title()

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
