from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Optional

from agents import Agent, FunctionTool, OpenAIChatCompletionsModel, Runner
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.tracing import set_tracing_disabled
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel

from rocky.contracts.agent import (
    RockyAgentConfig,
    RockyAgentStatus,
    RockyAgentStreamEvent,
    RockyAgentStreamEventKind,
)
from rocky.contracts.chat import (
    RockyAttachment,
    RockyChatMessage,
    RockyToolCall,
)
from rocky.contracts.model import RockyModelProviderName
from rocky.contracts.internal import RockyRuntimeState
from rocky.contracts.shell import RockyRuntimeShellEnvironment
from rocky.services.attachments import RockyAttachments
from rocky.agentic.tools.toolbox import RockyToolbox
from rocky.agentic.tools.shell_provider import ShellProvider, ShellType
from rocky.models.capabilities import RockyModelCapabilities
from rocky.prompts.agent import (
    ROCKY_AGENT_INSTRUCTIONS,
    ROCKY_TITLE_SUMMARY_INSTRUCTIONS,
)
from rocky.prompts.runtime import ROCKY_RUNTIME_DEVELOPER_MESSAGE_TEMPLATE
from rocky.worker import RockyWorker, RockyWorkerEmitter
from flut.flutter.foundation.change_notifier import ChangeNotifier

set_tracing_disabled(True)


AZURE_API_VERSION = "2024-10-21"


class _RockyAgentSession:
    def __init__(
        self,
        inner: Agent,
        client: AsyncAzureOpenAI | AsyncOpenAI | None = None,
    ) -> None:
        self.inner = inner
        self._client = client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class RockyAgent(ChangeNotifier):
    def __init__(self) -> None:
        super().__init__()
        self._config: Optional[RockyAgentConfig] = None
        self._ready_config: Optional[RockyAgentConfig] = None
        self._toolbox = RockyToolbox.from_runtime_resources([])
        self._input_list: list[dict[str, object]] = []
        self._rebuild_task: Optional[asyncio.Task] = None
        self._status: RockyAgentStatus = RockyAgentStatus.UNCONFIGURED
        self._last_runtime_fingerprint: Optional[str] = None

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
            RockyAgentStatus.THINKING,
            RockyAgentStatus.RESPONDING,
            RockyAgentStatus.EXECUTING,
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
        self._ready_config = None
        self._last_runtime_fingerprint = None
        if self._rebuild_task is not None and not self._rebuild_task.done():
            self._rebuild_task.cancel()
        self._rebuild_task = None
        if config is None:
            self._input_list = []
            self._toolbox = RockyToolbox.from_runtime_resources([])
            self._set_status(RockyAgentStatus.UNCONFIGURED)
            return
        supports_tools = RockyModelCapabilities.supports_function(config.model_profile)
        shell_profiles = config.shell_profiles if supports_tools else []
        self._toolbox = RockyToolbox.from_runtime_resources(
            shell_profiles,
            include_web=supports_tools,
            skills=config.skills if supports_tools else [],
            workspace_folder=config.workspace_folder,
        )
        self._set_status(RockyAgentStatus.INITIALIZING)
        self._rebuild_task = asyncio.create_task(self._rebuild(config, self._toolbox))

    def set_history(self, messages: list[RockyChatMessage]) -> None:
        self._input_list = [
            self._message_to_input_item(m)
            for m in messages
            if m.role in ("user", "assistant", "system", "developer")
        ]
        self.notifyListeners()

    async def stream_reply(
        self,
        user_text: str,
        attachments: list[RockyAttachment] = (),
    ) -> AsyncIterator[RockyAgentStreamEvent]:
        if self._config is None:
            raise RuntimeError("RockyAgent is not configured.")
        config = self._config
        toolbox = self._toolbox
        self._set_status(RockyAgentStatus.SENDING)
        if self._ready_config != config and self._rebuild_task is not None:
            await self._rebuild_task
            self._set_status(RockyAgentStatus.SENDING)
        if self._ready_config != config:
            raise RuntimeError("RockyAgent failed to initialize.")

        user_item = self._message_to_input_item(
            RockyChatMessage(
                role="user",
                content=user_text,
                attachments=list(attachments or []),
            )
        )
        runtime_developer_messages = self._runtime_developer_messages(config, toolbox)
        runtime_developer_items = [
            self._message_to_input_item(message)
            for message in runtime_developer_messages
        ]
        if self._input_list:
            conversation = (
                list(self._input_list) + runtime_developer_items + [user_item]
            )
        elif attachments or runtime_developer_items:
            conversation = runtime_developer_items + [user_item]
        else:
            conversation = user_text

        next_input: list[dict[str, object]] = []

        for message in runtime_developer_messages:
            yield RockyAgentStreamEvent(
                RockyAgentStreamEventKind.DEVELOPER_MESSAGE,
                message=message,
            )

        async def _produce(emit: RockyWorkerEmitter[RockyAgentStreamEvent]) -> None:
            session = self._build_session(
                config,
                ROCKY_AGENT_INSTRUCTIONS,
                "Rocky",
                toolbox.as_sdk_tools(),
            )
            try:
                result = Runner.run_streamed(session.inner, input=conversation)
                generation_started = False
                pending_tool_call_ids: list[str] = []
                async for event in result.stream_events():
                    if event.type == "raw_response_event":
                        if not generation_started:
                            generation_started = True
                            emit(
                                RockyAgentStreamEvent(
                                    RockyAgentStreamEventKind.GENERATION_STARTED
                                )
                            )
                        if isinstance(event.data, ResponseTextDeltaEvent):
                            delta = event.data.delta
                            if delta:
                                emit(
                                    RockyAgentStreamEvent(
                                        RockyAgentStreamEventKind.TEXT_DELTA,
                                        delta=delta,
                                    )
                                )
                    elif event.type == "run_item_stream_event":
                        if event.name == "tool_called":
                            tool_call = self._tool_call_payload(event.item)
                            if tool_call is None:
                                continue
                            if tool_call.id:
                                pending_tool_call_ids.append(tool_call.id)
                            emit(
                                RockyAgentStreamEvent(
                                    RockyAgentStreamEventKind.TOOL_STARTED,
                                    tool=tool_call,
                                )
                            )
                        elif event.name == "tool_output":
                            generation_started = False
                            call_id = (
                                pending_tool_call_ids.pop(0)
                                if pending_tool_call_ids
                                else ""
                            )
                            emit(
                                RockyAgentStreamEvent(
                                    RockyAgentStreamEventKind.TOOL_FINISHED,
                                    tool=self._tool_result_payload(event.item, call_id),
                                )
                            )
                        elif event.name == "reasoning_item_created":
                            emit(
                                RockyAgentStreamEvent(
                                    RockyAgentStreamEventKind.REASONING
                                )
                            )
                next_input.extend(result.to_input_list())
            finally:
                await session.close()

        try:
            async for event in RockyWorker.stream(_produce):
                if event.type == RockyAgentStreamEventKind.GENERATION_STARTED:
                    if self._status != RockyAgentStatus.RESPONDING:
                        self._set_status(RockyAgentStatus.RESPONDING)
                elif event.type == RockyAgentStreamEventKind.TEXT_DELTA:
                    if self._status != RockyAgentStatus.RESPONDING:
                        self._set_status(RockyAgentStatus.RESPONDING)
                    yield event
                elif event.type == RockyAgentStreamEventKind.TOOL_STARTED:
                    self._set_status(RockyAgentStatus.EXECUTING)
                    yield RockyAgentStreamEvent(
                        RockyAgentStreamEventKind.MESSAGE_BOUNDARY
                    )
                    yield event
                elif event.type == RockyAgentStreamEventKind.TOOL_FINISHED:
                    self._set_status(RockyAgentStatus.SENDING)
                    yield event
                elif event.type == RockyAgentStreamEventKind.REASONING:
                    if self._status != RockyAgentStatus.EXECUTING:
                        self._set_status(RockyAgentStatus.THINKING)
            self._input_list = list(next_input)
        finally:
            if self._status in (
                RockyAgentStatus.SENDING,
                RockyAgentStatus.THINKING,
                RockyAgentStatus.RESPONDING,
                RockyAgentStatus.EXECUTING,
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
            session = self._build_session(
                config,
                ROCKY_TITLE_SUMMARY_INSTRUCTIONS,
                "Rocky-Title-Summary",
            )
            try:
                result = await Runner.run(session.inner, input=conversation)
                return str(result.final_output or "").strip()
            finally:
                await session.close()

        return await RockyWorker.run_async(_summarize)

    async def _rebuild(
        self,
        config: RockyAgentConfig,
        toolbox: RockyToolbox,
    ) -> None:
        try:
            await RockyWorker.run_async(toolbox.initialize)
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._config == config:
                self._ready_config = None
            raise
        if self._config != config or self._toolbox is not toolbox:
            return
        self._ready_config = config
        self._set_status(RockyAgentStatus.READY)

    @staticmethod
    def _build_session(
        config: RockyAgentConfig,
        instructions: str,
        name: str,
        tools: list[FunctionTool] | None = None,
    ) -> _RockyAgentSession:
        model_profile = config.model_profile
        client: AsyncAzureOpenAI | AsyncOpenAI | None = None
        if model_profile.provider == RockyModelProviderName.LITERTLM:
            from rocky.models.providers.litertlm import LiteRtLmModel

            path = (model_profile.name or "").strip()
            if not path:
                raise ValueError("LiteRT-LM model file path is required.")
            model = LiteRtLmModel(path)
        elif model_profile.provider == RockyModelProviderName.AZURE_OPENAI:
            if not model_profile.endpoint:
                raise ValueError("endpoint is required for azure_openai")
            client = AsyncAzureOpenAI(
                api_key=model_profile.key,
                azure_endpoint=model_profile.endpoint,
                api_version=AZURE_API_VERSION,
            )
            backend_model = (
                model_profile.deployment or ""
            ).strip() or model_profile.name
            model = OpenAIChatCompletionsModel(
                model=backend_model,
                openai_client=client,
            )
        else:
            client = AsyncOpenAI(api_key=model_profile.key)
            model = OpenAIChatCompletionsModel(
                model=model_profile.name,
                openai_client=client,
            )

        return _RockyAgentSession(
            Agent(
                name=name,
                instructions=instructions,
                model=model,
                tools=list(tools or []),
            ),
            client,
        )

    @classmethod
    def _tool_call_payload(cls, item: object) -> RockyToolCall | None:
        if not isinstance(item, ToolCallItem):
            return None
        raw = item.raw_item
        if not isinstance(raw, ResponseFunctionToolCall):
            return None
        return RockyToolCall(
            id=raw.call_id,
            name=raw.name,
            arguments=cls._decode_tool_arguments(raw.arguments),
        )

    @classmethod
    def _tool_result_payload(cls, item: object, call_id: str) -> RockyToolCall | None:
        if not isinstance(item, ToolCallOutputItem):
            return None
        output = item.output
        return RockyToolCall(
            id=call_id,
            output=cls._jsonable_tool_value(output),
            completed=True,
        )

    @classmethod
    def _decode_tool_arguments(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return cls._jsonable_tool_value(value)

    @staticmethod
    def _jsonable_tool_value(value: object) -> object:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {
                str(k): RockyAgent._jsonable_tool_value(v) for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [RockyAgent._jsonable_tool_value(v) for v in value]
        if isinstance(value, BaseModel):
            return value.model_dump(exclude_unset=True)
        return str(value)

    def _runtime_state(
        self,
        config: Optional[RockyAgentConfig] = None,
        toolbox: Optional[RockyToolbox] = None,
    ) -> RockyRuntimeState:
        config = config or self._config
        toolbox = toolbox or self._toolbox
        shell_profiles = list(config.shell_profiles) if config is not None else []
        skills = list(config.skills) if config is not None else []
        active_shell_ids = set(toolbox.shells.keys())
        environments = [
            RockyRuntimeShellEnvironment(
                id=shell_profile.id,
                name=shell_profile.display_name or shell_profile.shell_type,
                kind=(
                    "local"
                    if shell_profile.shell_type == ShellType.LOCAL.value
                    else "remote"
                ),
                os=(
                    ShellProvider.local_os()
                    if shell_profile.shell_type == ShellType.LOCAL.value
                    else None
                ),
            )
            for shell_profile in shell_profiles
            if shell_profile.id in active_shell_ids
        ]
        return RockyRuntimeState(shell_environments=environments, skills=skills)

    def _runtime_developer_messages(
        self,
        config: Optional[RockyAgentConfig] = None,
        toolbox: Optional[RockyToolbox] = None,
    ) -> list[RockyChatMessage]:
        state = self._runtime_state(config, toolbox)
        fingerprint = state.fingerprint()
        if fingerprint == self._last_runtime_fingerprint:
            return []
        self._last_runtime_fingerprint = fingerprint
        body = ROCKY_RUNTIME_DEVELOPER_MESSAGE_TEMPLATE.format(
            RUNTIME_STATE=state.model_context_json(indent=2)
        )
        return [RockyChatMessage(role="developer", content=body)]

    @staticmethod
    def _message_to_input_item(message: RockyChatMessage) -> dict[str, object]:
        text = message.content or ""
        attachments = list(message.attachments or [])
        if not attachments:
            return {"role": message.role, "content": text}

        parts: list[dict[str, object]] = []
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
