import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, List, Union

from rocky.agentic.contracts.tools import (
    FunctionDefinition,
    JsonSchema,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from rocky.agentic.tools.shell_provider import ShellProvider


class Tool:
    name: str
    callbacks: Dict[str, Any]

    def __init__(self, name: str):
        self.name = name
        self.callbacks = {}
        self._config: Dict[str, Any] = {}

    def set_config(self, config: Dict[str, Any]) -> None:
        """Set the full configuration dictionary for this tool."""
        self._config = config

    def get_config(self, namespace: str, default: Any = None) -> Any:
        """Get configuration for a specific namespace key."""
        return self._config.get(namespace, default)

    def get_tool_definition(self) -> ToolDefinition:
        raise NotImplementedError(f"Tool {self.name} missing get_tool_definition")

    def get_developer_messages(self) -> List[str]:
        return []

    def get_post_tool_developer_messages(
        self,
        tool_call: ToolCall,
        tool_result: ToolResult,
    ) -> List[str]:
        return []

    def register_callback(
        self,
        function_name: str,
        callback: Union[
            Callable[[ToolCall], ToolResult],
            Callable[[ToolCall], Awaitable[ToolResult]],
        ],
    ) -> None:
        if not self.callbacks:
            self.callbacks = {}
        self.callbacks[function_name] = callback

    async def initialize(self) -> None:
        """Initialize the tool. Override to perform setup."""
        pass

    async def handle_tool_call(self, tool_call: ToolCall) -> ToolResult:
        if self.callbacks and tool_call.function in self.callbacks:
            callback = self.callbacks[tool_call.function]
            if asyncio.iscoroutinefunction(callback):
                return await callback(tool_call)
            else:
                return await asyncio.to_thread(callback, tool_call)
        else:
            raise NotImplementedError(
                f"Tool {self.name} does not implement function {tool_call.function}"
            )

    def request_shell() -> ShellProvider:
        raise NotImplementedError()

    @staticmethod
    def load_tool_definition(filename: str) -> ToolDefinition:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "tools" not in data:
            raise ValueError(f"Missing 'tools' key in {filename}")

        tools = data["tools"]
        if not isinstance(tools, list):
            raise ValueError(f"'tools' must be a list in {filename}")

        # Count function_group entries
        function_groups = [t for t in tools if t.get("type") == "function_group"]
        if len(function_groups) != 1:
            raise ValueError(
                f"Expected exactly 1 function_group, found {len(function_groups)} in {filename}"
            )

        functions: List[FunctionDefinition] = []
        group = function_groups[0]

        for tool in tools:
            tool_type = tool.get("type")

            if tool_type == "function":
                parameters = None
                if "parameters" in tool:
                    parameters = JsonSchema.model_validate(tool["parameters"])

                functions.append(
                    FunctionDefinition(
                        name=tool.get("name", ""),
                        description=tool.get("description", ""),
                        parameters=parameters,
                        strict=tool.get("strict", False),
                    )
                )

        return ToolDefinition(
            functions=functions,
            name=group.get("name"),
            description=group.get("description"),
            channel=group.get("channel"),
            unconstrained=group.get("unconstrained", False),
        )

    @staticmethod
    def extract_arguments_as_str(
        arguments: Dict | str, extra_keys: list[str] = []
    ) -> str:
        if isinstance(arguments, str):
            return arguments
        if not isinstance(arguments, dict):
            raise ValueError(
                "Tool arguments should be a string or a dict containing 'arguments' or one of the tolerated string keys."
            )
        tolerated_keys = tuple(extra_keys)
        for key in tolerated_keys:
            if key in arguments:
                value = arguments.get(key, "")
                if not isinstance(value, str):
                    raise ValueError(
                        f"Tool arguments dict should contain '{key}' as a string."
                    )
                return value
        if "arguments" not in arguments:
            tolerated_keys_desc = ", ".join(repr(key) for key in tolerated_keys)
            extra_desc = (
                f" or keys: {tolerated_keys_desc}" if tolerated_keys_desc else ""
            )
            raise ValueError(
                "Tool arguments should be a string or a dict containing 'arguments' as a string"
                + extra_desc
                + ". "
                + str(arguments)
            )
        args = arguments.get("arguments", "")
        if not isinstance(args, str):
            raise ValueError(
                "Tool arguments dict should contain 'arguments' as a string."
            )
        return args

    @staticmethod
    def extract_cmd(arguments: Dict) -> List[str]:
        if "cmd" in arguments:
            cmd = arguments.get("cmd", [])
        elif "arguments" in arguments:
            cmd = arguments.get("arguments", [])
        else:
            raise ValueError(
                "No 'cmd' or 'arguments' found in arguments." + str(arguments)
            )
        # The model tends to use 'cmd' as a string or pass the entire arguments as a string,
        # regardless of the schema definition. It should be harmless to execute a string
        # as a bash command.
        if isinstance(cmd, str):
            cmd = ["bash", "-lc", cmd]
        if not isinstance(cmd, list):
            raise ValueError("'cmd' should be a list of strings.")
        for part in cmd:
            if not isinstance(part, str):
                raise ValueError("All parts of 'cmd' should be strings.")
        return cmd
