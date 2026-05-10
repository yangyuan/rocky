from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import os
from typing import AsyncIterator, Optional

from agents import (
    Agent,
    FunctionTool,
    OpenAIChatCompletionsModel,
    OpenAIResponsesModel,
    Runner,
)
from agents.mcp import MCPServerManager
from agents.stream_events import StreamEvent
from agents.tracing import set_tracing_disabled
from openai import AsyncAzureOpenAI, AsyncOpenAI

from rocky.contracts.agent import (
    RockyAgentConfig,
    RockyAgentStatus,
    RockyChatChunkEvent,
    RockyStreamEvent,
)
from rocky.contracts.chat import (
    RockyChatContent,
    RockyChatFileContentPart,
    RockyChatImageContentPart,
    RockyChatMessage,
    RockyChatContentPart,
    RockyChatContentPartType,
    RockyChatTextContentPart,
)
from rocky.contracts.mcp import (
    RockyHttpMcpServerProperties,
    RockyMcpServerProfile,
    RockyMcpServerType,
    RockyRuntimeMcpServer,
    RockyStdioMcpServerProperties,
)
from rocky.contracts.model import RockyModelApi, RockyModelProviderName
from rocky.contracts.internal import RockyRuntimeState
from rocky.contracts.shell import RockyRuntimeShellEnvironment
from rocky.agentic.tools.toolbox import RockyToolbox
from rocky.agentic.tools.shell_provider import ShellProvider, ShellType
from rocky.models.capabilities import RockyModelCapabilities
from rocky.prompts.agent import (
    ROCKY_AGENT_IDENTITY,
    ROCKY_AGENT_INSTRUCTION,
    ROCKY_AGENT_PERSONALITY,
)
from rocky.prompts.app import ROCKY_TITLE_SUMMARY_INSTRUCTIONS
from rocky.prompts.runtime import ROCKY_RUNTIME_DEVELOPER_MESSAGE_TEMPLATE
from rocky.services.streaming import RockyStreaming
from rocky.worker import RockyWorker, RockyWorkerEmitter
from flut.flutter.foundation.change_notifier import ChangeNotifier

set_tracing_disabled(True)


AZURE_API_VERSION = "2024-10-21"
ROCKY_AGENT_MAX_TURNS = 100


class _RockyAgentSession:
    def __init__(
        self,
        inner: Agent,
        client: AsyncAzureOpenAI | AsyncOpenAI | None = None,
        mcp_manager: MCPServerManager | None = None,
    ) -> None:
        self.inner = inner
        self._client = client
        self._mcp_manager = mcp_manager

    async def close(self) -> None:
        if self._mcp_manager is not None:
            await self._mcp_manager.cleanup_all()
        if self._client is not None:
            await self._client.close()


class RockyAgent(ChangeNotifier):
    def __init__(self) -> None:
        super().__init__()
        self._config: Optional[RockyAgentConfig] = None
        self._ready_config: Optional[RockyAgentConfig] = None
        self._toolbox = RockyToolbox.from_runtime_resources([])
        self._history: list[RockyChatMessage] = []
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
            self._history = []
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
        self._history = [message.model_copy(deep=True) for message in messages]
        self.notifyListeners()

    async def stream_reply(
        self,
        user_content: RockyChatContent,
    ) -> AsyncIterator[RockyStreamEvent]:
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

        user_message = RockyChatMessage(
            role="user",
            content=user_content,
        )
        runtime_developer_messages = self._runtime_developer_messages(config, toolbox)
        if self._history:
            conversation = (
                list(self._history) + runtime_developer_messages + [user_message]
            )
        elif runtime_developer_messages:
            conversation = runtime_developer_messages + [user_message]
        else:
            conversation = [user_message]

        for message in runtime_developer_messages:
            yield message

        async def _produce(emit: RockyWorkerEmitter[StreamEvent]) -> None:
            async with self._build_session(
                config,
                "\n\n".join(
                    [
                        ROCKY_AGENT_IDENTITY,
                        ROCKY_AGENT_PERSONALITY,
                        ROCKY_AGENT_INSTRUCTION,
                    ]
                ),
                "Rocky",
                toolbox.as_sdk_tools(),
            ) as session:
                result = Runner.run_streamed(
                    session.inner,
                    input=self._messages_to_sdk_input(conversation),
                    max_turns=ROCKY_AGENT_MAX_TURNS,
                )
                async for event in result.stream_events():
                    emit(event)

        try:
            streaming = RockyStreaming()
            async for item in streaming.stream(RockyWorker.stream(_produce)):
                if isinstance(item, RockyChatChunkEvent) and item.state is not None:
                    self._set_status(item.state)
                yield item
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
        if config.model_profile.provider == RockyModelProviderName.LITERTLM:
            return ""
        conversation: list[dict[str, object]] = []
        for message in messages:
            if message.role not in ("user", "assistant"):
                continue
            text = self._message_text(message)
            if text:
                conversation.append({"role": message.role, "content": text})
        if not conversation:
            return ""

        async def _summarize() -> str:
            async with self._build_session(
                config,
                ROCKY_TITLE_SUMMARY_INSTRUCTIONS,
                "Rocky-Title-Summary",
                include_mcp=False,
            ) as session:
                result = await Runner.run(session.inner, input=conversation)
                return str(result.final_output or "").strip()

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

    @classmethod
    @asynccontextmanager
    async def _build_session(
        cls,
        config: RockyAgentConfig,
        instructions: str,
        name: str,
        tools: list[FunctionTool] | None = None,
        include_mcp: bool = True,
    ) -> AsyncIterator[_RockyAgentSession]:
        model_profile = config.model_profile
        client: AsyncAzureOpenAI | AsyncOpenAI | None = None
        backend_model: str | None = None
        supports_tools = RockyModelCapabilities.supports_function(config.model_profile)
        selected_mcp_profiles = (
            list(config.mcp_server_profiles) if include_mcp and supports_tools else []
        )
        match model_profile.provider:
            case RockyModelProviderName.LITERTLM:
                from rocky.models.providers.litertlm import LitertLmModel

                path = (model_profile.name or "").strip()
                if not path:
                    raise ValueError("LiteRT-LM model file path is required.")
                model = LitertLmModel(path)
            case RockyModelProviderName.AZURE_OPENAI:
                if not model_profile.endpoint:
                    raise ValueError("endpoint is required for azure_openai")
                deployment = (model_profile.deployment or "").strip() or None
                client = AsyncAzureOpenAI(
                    api_key=model_profile.key,
                    azure_endpoint=model_profile.endpoint,
                    azure_deployment=deployment,
                    api_version=AZURE_API_VERSION,
                    default_headers=model_profile.headers or None,
                )
                backend_model = model_profile.name
            case RockyModelProviderName.OPENAI_COMPATIBLE:
                if not model_profile.endpoint:
                    raise ValueError("endpoint is required for openai_compatible")
                client = AsyncOpenAI(
                    api_key=model_profile.key,
                    base_url=model_profile.endpoint,
                    default_headers=model_profile.headers or None,
                )
                backend_model = model_profile.name
            case _:
                client = AsyncOpenAI(
                    api_key=model_profile.key,
                    default_headers=model_profile.headers or None,
                )
                backend_model = model_profile.name

        if backend_model is not None:
            if client is None:
                raise RuntimeError("OpenAI client was not initialized.")
            match model_profile.api:
                case RockyModelApi.RESPONSES:
                    model = OpenAIResponsesModel(
                        model=backend_model,
                        openai_client=client,
                    )
                case _:
                    model = OpenAIChatCompletionsModel(
                        model=backend_model,
                        openai_client=client,
                    )

        sdk_tools: list[object] = list(tools or [])
        mcp_servers: list[object] = []
        mcp_manager: MCPServerManager | None = None
        if selected_mcp_profiles:
            mcp_manager = MCPServerManager(
                [cls._mcp_server(profile) for profile in selected_mcp_profiles],
                connect_in_parallel=True,
            )
            try:
                await mcp_manager.connect_all()
                mcp_servers = mcp_manager.active_servers
            except Exception:
                await mcp_manager.cleanup_all()
                if client is not None:
                    await client.close()
                raise

        try:
            session = _RockyAgentSession(
                Agent(
                    name=name,
                    instructions=instructions,
                    model=model,
                    tools=sdk_tools,
                    mcp_servers=mcp_servers,
                    mcp_config={"convert_schemas_to_strict": False},
                ),
                client,
                mcp_manager,
            )
        except Exception:
            if mcp_manager is not None:
                await mcp_manager.cleanup_all()
            if client is not None:
                await client.close()
            raise
        try:
            yield session
        finally:
            await session.close()

    @classmethod
    def _mcp_server(cls, profile: RockyMcpServerProfile) -> object:
        from agents.mcp import MCPServerStdio, MCPServerStreamableHttp

        kwargs: dict[str, object] = {"cache_tools_list": True}
        if profile.timeout is not None:
            kwargs["client_session_timeout_seconds"] = profile.timeout
        if profile.server_type == RockyMcpServerType.STDIO:
            properties = profile.properties
            if not isinstance(properties, RockyStdioMcpServerProperties):
                properties = RockyStdioMcpServerProperties()
            return MCPServerStdio(
                name=cls._mcp_server_label(profile),
                params=cls._stdio_mcp_params(properties.command),
                **kwargs,
            )
        properties = profile.properties
        if not isinstance(properties, RockyHttpMcpServerProperties):
            properties = RockyHttpMcpServerProperties()
        params: dict[str, object] = {"url": properties.url}
        if properties.headers:
            params["headers"] = dict(properties.headers)
        if profile.timeout is not None:
            params["timeout"] = profile.timeout
        return MCPServerStreamableHttp(
            name=cls._mcp_server_label(profile),
            params=params,
            **kwargs,
        )

    @staticmethod
    def _stdio_mcp_params(command_line: str) -> dict[str, object]:
        command = (command_line or "").strip()
        if not command:
            return {"command": ""}
        if os.name == "nt":
            return {"command": "cmd.exe", "args": ["/d", "/s", "/c", command]}
        return {"command": "/bin/sh", "args": ["-lc", command]}

    @staticmethod
    def _mcp_server_label(profile: RockyMcpServerProfile) -> str:
        display = (profile.display_name or "").strip()
        if display:
            return display
        return profile.id

    def _runtime_state(
        self,
        config: Optional[RockyAgentConfig] = None,
        toolbox: Optional[RockyToolbox] = None,
    ) -> RockyRuntimeState:
        config = config or self._config
        toolbox = toolbox or self._toolbox
        shell_profiles = list(config.shell_profiles) if config is not None else []
        skills = list(config.skills) if config is not None else []
        mcp_server_profiles = (
            list(config.mcp_server_profiles) if config is not None else []
        )
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
        mcp_servers = [
            RockyRuntimeMcpServer(
                id=mcp_server.id,
                name=self._mcp_server_label(mcp_server),
                type=mcp_server.server_type,
            )
            for mcp_server in mcp_server_profiles
        ]
        return RockyRuntimeState(
            shell_environments=environments,
            skills=skills,
            mcp_servers=mcp_servers,
        )

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

    @classmethod
    def _messages_to_sdk_input(
        cls,
        messages: list[RockyChatMessage],
    ) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for message in messages:
            items.extend(cls._message_to_sdk_input_items(message))
        return items

    @staticmethod
    def _message_to_sdk_input_items(
        message: RockyChatMessage,
    ) -> list[dict[str, object]]:
        content = RockyAgent._content_to_input_content(message.content)
        item: dict[str, object] = {
            "role": message.role,
            "content": content,
        }
        if message.role == "tool":
            return [
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id or "",
                    "output": content,
                }
            ]
        if message.tool_calls:
            items: list[dict[str, object]] = []
            if RockyAgent._message_text(message).strip():
                items.append(item)
            items.extend(
                {
                    "type": "function_call",
                    "call_id": tool.id,
                    "name": tool.name,
                    "arguments": RockyAgent._function_arguments(tool.arguments),
                }
                for tool in message.tool_calls
            )
            return items
        if message.tool_call_id is not None:
            item["tool_call_id"] = message.tool_call_id
        return [item]

    @staticmethod
    def _function_arguments(arguments: dict | str) -> str:
        if isinstance(arguments, str):
            return arguments
        return json.dumps(arguments, ensure_ascii=False, default=str)

    @staticmethod
    def _content_to_input_content(
        content: Optional[RockyChatContent],
    ) -> str | list[dict[str, object]]:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        parts: list[dict[str, object]] = []
        for part in content:
            if isinstance(
                part,
                (
                    RockyChatTextContentPart,
                    RockyChatImageContentPart,
                    RockyChatFileContentPart,
                ),
            ):
                parts.append(RockyAgent._content_part_input_dict(part))
            else:
                return json.dumps(content, ensure_ascii=False, default=str)
        return parts

    @staticmethod
    def _content_part_dict(part: RockyChatContentPart) -> dict[str, object]:
        return part.model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _content_part_input_dict(part: RockyChatContentPart) -> dict[str, object]:
        value = RockyAgent._content_part_dict(part)
        match part.type:
            case RockyChatContentPartType.TEXT:
                value["type"] = "input_text"
            case RockyChatContentPartType.IMAGE:
                value["type"] = "input_image"
            case RockyChatContentPartType.FILE:
                value["type"] = "input_file"
        return value

    @staticmethod
    def _message_text(message: RockyChatMessage) -> str:
        content = message.content
        if isinstance(content, str):
            return content
        if content is None:
            return ""
        parts: list[str] = []
        for part in content:
            if isinstance(part, RockyChatTextContentPart):
                parts.append(part.text)
        return "\n".join(parts)
