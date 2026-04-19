from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from agents import Agent, OpenAIChatCompletionsModel, Runner
from agents.tracing import set_tracing_disabled
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from rocky.contracts.agent import RockyAgentConfig, RockyAgentStatus
from rocky.contracts.chat import RockyAttachment, RockyChatMessage
from rocky.agentic.attachments import RockyAttachments
from rocky.worker import RockyWorker, RockyWorkerEmitter
from flut.flutter.foundation.change_notifier import ChangeNotifier

set_tracing_disabled(True)


DEFAULT_INSTRUCTIONS = (
    "You are Rocky, a concise and friendly desktop assistant. "
    "Answer clearly, format code with Markdown fences, and keep replies tight."
)
TITLE_INSTRUCTIONS = (
    "You write very short chat titles that summarize the conversation. "
    "Respond with ONLY the title text. No quotes, no trailing punctuation, "
    "no prefix like 'Title:'. Aim for 5 tokens, never exceed 10 tokens."
)
AZURE_API_VERSION = "2024-10-21"


class RockyAgent(ChangeNotifier):
    def __init__(self) -> None:
        super().__init__()
        self._config: Optional[RockyAgentConfig] = None
        self._inner: Optional[Agent] = None
        self._input_list: list[dict[str, str]] = []
        self._rebuild_task: Optional[asyncio.Task] = None
        self._status: RockyAgentStatus = RockyAgentStatus.UNCONFIGURED

    @property
    def config(self) -> Optional[RockyAgentConfig]:
        return self._config

    @property
    def status(self) -> RockyAgentStatus:
        return self._status

    @property
    def busy(self) -> bool:
        return self._status in (
            RockyAgentStatus.SENDING,
            RockyAgentStatus.RESPONDING,
        )

    def _set_status(self, status: RockyAgentStatus) -> None:
        if self._status == status:
            return
        self._status = status
        self.notifyListeners()

    def configure(self, config: Optional[RockyAgentConfig]) -> None:
        if config == self._config:
            return
        self._config = config
        self._inner = None
        if self._rebuild_task is not None and not self._rebuild_task.done():
            self._rebuild_task.cancel()
        self._rebuild_task = None
        if config is None:
            self._input_list = []
            self._set_status(RockyAgentStatus.UNCONFIGURED)
            return
        self._set_status(RockyAgentStatus.INITIALIZING)
        self._rebuild_task = asyncio.create_task(self._rebuild(config))

    def set_history(self, messages: list[RockyChatMessage]) -> None:
        self._input_list = [
            self._message_to_input_item(m)
            for m in messages
            if m.role in ("user", "assistant", "system")
        ]
        self.notifyListeners()

    async def stream_reply(
        self,
        user_text: str,
        attachments: list[RockyAttachment] = (),
    ) -> AsyncIterator[str]:
        if self._config is None:
            raise RuntimeError("RockyAgent is not configured.")
        self._set_status(RockyAgentStatus.SENDING)
        if self._inner is None and self._rebuild_task is not None:
            await self._rebuild_task
            self._set_status(RockyAgentStatus.SENDING)
        if self._inner is None:
            raise RuntimeError("RockyAgent failed to initialize.")

        user_item = self._message_to_input_item(
            RockyChatMessage(
                role="user",
                content=user_text,
                attachments=list(attachments or []),
            )
        )
        if self._input_list:
            conversation = list(self._input_list) + [user_item]
        elif attachments:
            conversation = [user_item]
        else:
            conversation = user_text

        inner = self._inner
        next_input: list[dict] = []

        async def _produce(emit: RockyWorkerEmitter[str]) -> None:
            result = Runner.run_streamed(inner, input=conversation)
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    delta = event.data.delta
                    if delta:
                        emit(delta)
            next_input.extend(result.to_input_list())

        try:
            async for delta in RockyWorker.stream(_produce):
                if self._status != RockyAgentStatus.RESPONDING:
                    self._set_status(RockyAgentStatus.RESPONDING)
                yield delta
            self._input_list = next_input
        finally:
            if self._status in (
                RockyAgentStatus.SENDING,
                RockyAgentStatus.RESPONDING,
            ):
                self._set_status(RockyAgentStatus.READY)

    async def summarize_title(self, messages: list[RockyChatMessage]) -> str:
        if self._config is None:
            raise RuntimeError("RockyAgent is not configured.")
        config = self._config
        conversation = [
            {"role": m.role, "content": m.content or ""}
            for m in messages
            if m.role in ("user", "assistant") and not m.streaming and m.content
        ]
        if not conversation:
            return ""

        async def _summarize() -> str:
            inner = self._build_inner(config, TITLE_INSTRUCTIONS, "Rocky-Title")
            result = await Runner.run(inner, input=conversation)
            return str(result.final_output or "").strip()

        return await RockyWorker.run_async(_summarize)

    async def _rebuild(self, config: RockyAgentConfig) -> None:
        try:
            inner = await RockyWorker.run(
                self._build_inner, config, DEFAULT_INSTRUCTIONS, "Rocky"
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._config == config:
                self._inner = None
            raise
        if self._config != config:
            return
        self._inner = inner
        self._set_status(RockyAgentStatus.READY)

    @staticmethod
    def _build_inner(config: RockyAgentConfig, instructions: str, name: str) -> Agent:
        profile = config.model_profile
        if profile.provider == "litertlm":
            from rocky.models.providers.litertlm import LiteRtLmModel

            path = (profile.name or "").strip()
            if not path:
                raise ValueError("LiteRT-LM model file path is required.")
            model = LiteRtLmModel(path)
        elif profile.provider == "azure_openai":
            if not profile.endpoint:
                raise ValueError("endpoint is required for azure_openai")
            client = AsyncAzureOpenAI(
                api_key=profile.key,
                azure_endpoint=profile.endpoint,
                api_version=AZURE_API_VERSION,
            )
            backend_model = (profile.deployment or "").strip() or profile.name
            model = OpenAIChatCompletionsModel(
                model=backend_model,
                openai_client=client,
            )
        else:
            client = AsyncOpenAI(api_key=profile.key)
            model = OpenAIChatCompletionsModel(
                model=profile.name,
                openai_client=client,
            )

        return Agent(
            name=name,
            instructions=instructions,
            model=model,
        )

    @staticmethod
    def _message_to_input_item(message: RockyChatMessage) -> dict:
        text = message.content or ""
        attachments = list(message.attachments or [])
        if not attachments:
            return {"role": message.role, "content": text}

        parts: list[dict] = []
        if text:
            parts.append({"type": "input_text", "text": text})
        for attachment in attachments:
            if RockyAttachments.is_image(attachment):
                parts.append(
                    {
                        "type": "input_image",
                        "image_url": RockyAttachments.data_url(attachment),
                    }
                )
            else:
                body = (
                    RockyAttachments.decoded_text(attachment)
                    if RockyAttachments.is_text(attachment)
                    else ""
                )
                parts.append(
                    {
                        "type": "input_text",
                        "text": (
                            f"[Attached file: {attachment.filename}]\n"
                            f"```\n{body}\n```"
                        ),
                    }
                )
        return {"role": message.role, "content": parts}
