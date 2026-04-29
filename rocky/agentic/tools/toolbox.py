from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from agents import FunctionTool, ToolOutputImage, ToolOutputText

from rocky.agentic.contracts.message import MessageContentImage, MessageContentText
from rocky.agentic.contracts.skill import Skill
from rocky.agentic.contracts.tools import ToolCall, ToolDefinition, ToolResult
from rocky.agentic.tools.shell import ShellTool
from rocky.agentic.tools.shell_provider import ShellProvider, ShellType
from rocky.agentic.tools.skill import SkillTool
from rocky.agentic.tools.tool import Tool
from rocky.agentic.tools.web import WebTool
from rocky.contracts.shell import RockyShellProfile

logger = logging.getLogger(__name__)


class RockyToolbox:
    def __init__(
        self,
        tools: list[Tool],
        shells: Optional[dict[str, ShellProvider]] = None,
    ):
        self.tools: dict[str, Tool] = {tool.name: tool for tool in tools}
        self.shells = dict(shells or {})

    @classmethod
    def from_runtime_resources(
        cls,
        shell_profiles: list[RockyShellProfile] | None,
        include_web: bool = False,
        skills: list[Skill] | None = None,
    ) -> "RockyToolbox":
        shells = cls._build_shells(shell_profiles or [])
        tools: list[Tool] = []
        if include_web:
            tools.append(WebTool())
        if shells:
            tools.append(ShellTool(shells))
        if skills:
            tools.append(SkillTool(skills))
        return cls(tools=tools, shells=shells)

    @classmethod
    def _build_shells(
        cls,
        profiles: list[RockyShellProfile],
    ) -> dict[str, ShellProvider]:
        shells: dict[str, ShellProvider] = {}
        for profile in profiles:
            shell = cls._build_shell(profile)
            if shell is not None:
                shells[profile.id] = shell
        return shells

    @staticmethod
    def _build_shell(
        profile: RockyShellProfile | None,
    ) -> Optional[ShellProvider]:
        if profile is None:
            return None
        try:
            shell_type = ShellType(profile.shell_type)
        except ValueError:
            logger.warning("Unsupported shell type: %s", profile.shell_type)
            return None
        shell_name = profile.name.strip()
        if not shell_name and shell_type in (
            ShellType.DOCKER,
            ShellType.DOCKER_IN_WSL,
            ShellType.DOCKER_OVER_SSH,
        ):
            logger.warning("Shell name is required for shell type %s.", shell_type)
            return None
        return ShellProvider(
            shell_name=shell_name,
            shell_type=shell_type,
            shell_host=profile.host.strip() or None,
            output_max_head_tail=profile.output_max_head_tail,
        )

    async def initialize(self) -> None:
        for shell in self.shells.values():
            await shell.initialize()
        for tool in self.tools.values():
            await tool.initialize()

    def as_sdk_tools(self) -> list[FunctionTool]:
        sdk_tools: list[FunctionTool] = []
        for definition in self.get_tool_definitions():
            if not definition.name:
                continue
            for function in definition.functions:
                sdk_name = self._sdk_tool_name(definition.name, function.name)
                sdk_tools.append(
                    FunctionTool(
                        name=sdk_name,
                        description=function.description,
                        params_json_schema=self._schema_dict(function.parameters),
                        on_invoke_tool=self._make_sdk_handler(
                            sdk_name=sdk_name,
                            definition=definition,
                            function_name=function.name,
                        ),
                        strict_json_schema=function.strict,
                    )
                )
        return sdk_tools

    def get_tool_definitions(self) -> list[ToolDefinition]:
        return [tool.get_tool_definition() for tool in self.tools.values()]

    async def handle_tool_call(self, tool_call: ToolCall) -> ToolResult:
        tool = self.tools.get(tool_call.namespace)
        if tool is None:
            raise RuntimeError(f"Tool {tool_call.namespace} not found in toolbox.")
        return await tool.handle_tool_call(tool_call)

    def _make_sdk_handler(
        self,
        *,
        sdk_name: str,
        definition: ToolDefinition,
        function_name: str,
    ):
        async def handle(_context: object, raw_arguments: str) -> Any:
            if definition.name is None:
                raise RuntimeError(f"Tool {sdk_name} has no namespace.")
            tool_call = ToolCall(
                call_id=f"{sdk_name}-{uuid.uuid4().hex}",
                namespace=definition.name,
                function=function_name,
                arguments=self._arguments(raw_arguments),
            )
            result = await self.handle_tool_call(tool_call)
            return self._sdk_result(result)

        return handle

    @staticmethod
    def _sdk_tool_name(namespace: str, function_name: str) -> str:
        return f"{namespace}__{function_name}"

    @staticmethod
    def _schema_dict(parameters: Any) -> dict[str, Any]:
        if parameters is None:
            return {"type": "object", "properties": {}}
        return parameters.model_dump(exclude_none=True)

    @staticmethod
    def _arguments(raw_arguments: str) -> dict[str, Any] | str:
        try:
            parsed = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            return {"arguments": raw_arguments}
        if isinstance(parsed, dict):
            return parsed
        return {"arguments": parsed}

    @staticmethod
    def _sdk_result(result: ToolResult) -> Any:
        output = result.output
        if isinstance(output, list):
            converted: list[Any] = []
            for item in output:
                if isinstance(item, MessageContentImage):
                    converted.append(ToolOutputImage(image_url=item.image_url))
                elif isinstance(item, MessageContentText):
                    converted.append(ToolOutputText(text=item.text))
                else:
                    converted.append(str(item))
            return converted
        if isinstance(output, dict):
            return json.dumps(output, ensure_ascii=False)
        return "" if output is None else str(output)
