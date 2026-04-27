import json

from rocky.agentic.contracts.message import MessageContentImage
from rocky.agentic.contracts.tools import (
    FunctionDefinition,
    JsonSchema,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from rocky.agentic.tools.shell_provider import ShellProvider
from rocky.agentic.tools.tool import Tool
from rocky.contracts.shell import RockyShellProfile, RockyShellReference

SHELL_TOOL_DEFINITION = ToolDefinition(
    name="shell",
    description="Utilities for running commands in a selected environment.",
    channel="commentary",
    unconstrained=True,
    functions=[
        FunctionDefinition(
            name="exec",
            description=(
                "Run a command in the requested environment and return stdout/stderr. "
                "Pass `cmd` as an array of command arguments. `workdir` is supported. "
                "`timeout` is interpreted as milliseconds when provided."
            ),
            parameters=JsonSchema.model_validate(
                {
                    "type": "object",
                    "properties": {
                        "shell_id": {"type": "string"},
                        "cmd": {"type": "array", "items": {"type": "string"}},
                        "workdir": {"type": "string", "default": None},
                        "timeout": {"type": "number", "default": None},
                    },
                    "required": ["shell_id", "cmd"],
                }
            ),
            strict=False,
        ),
        FunctionDefinition(
            name="open_image",
            description=(
                "Returns the image in the environment at the given absolute path "
                "(only absolute paths supported). Supports jpg, jpeg, png, gif, "
                "and webp image formats."
            ),
            parameters=JsonSchema.model_validate(
                {
                    "type": "object",
                    "properties": {
                        "shell_id": {"type": "string"},
                        "path": {"type": "string"},
                    },
                    "required": ["shell_id", "path"],
                }
            ),
            strict=False,
        ),
        FunctionDefinition(
            name="download",
            description="Download a file from a URL into the environment filesystem.",
            parameters=JsonSchema.model_validate(
                {
                    "type": "object",
                    "properties": {
                        "shell_id": {"type": "string"},
                        "url": {"type": "string"},
                        "filepath": {"type": "string"},
                    },
                    "required": ["shell_id", "url", "filepath"],
                }
            ),
            strict=False,
        ),
    ],
)


class ShellTool(Tool):
    def __init__(
        self,
        shells: dict[str, ShellProvider],
        profiles: list[RockyShellProfile],
    ):
        super().__init__("shell")
        self.shells = dict(shells)
        self.profiles = list(profiles)
        self.register_callback("exec", self.handle_exec)
        self.register_callback("download", self.handle_download)
        self.register_callback("open_image", self.handle_open_image)

    def get_tool_definition(self) -> ToolDefinition:
        return SHELL_TOOL_DEFINITION

    def get_developer_messages(self) -> list[str]:
        shells = [
            RockyShellReference(
                id=profile.id,
                name=profile.display_name or "Untitled environment",
            )
            for profile in self.profiles
            if profile.id in self.shells
        ]
        if not shells:
            return []
        return [
            "Available environments for shell tools:\n"
            + json.dumps(
                [shell.model_dump() for shell in shells],
                ensure_ascii=False,
            )
            + "\nEvery shell tool call must include one of these IDs as `shell_id`. "
            + "Do not invent shell IDs."
        ]

    def _shell(self, tool_call: ToolCall) -> ShellProvider | ToolResult:
        if not isinstance(tool_call.arguments, dict):
            return ToolResult(
                call_id=tool_call.id,
                output="Shell tool arguments must be an object with shell_id.",
            )
        shell_id = tool_call.arguments.get("shell_id", "")
        if not isinstance(shell_id, str) or not shell_id.strip():
            return ToolResult(
                call_id=tool_call.id,
                output="Missing required argument: shell_id",
            )
        shell = self.shells.get(shell_id)
        if shell is None:
            available = ", ".join(sorted(self.shells)) or "none"
            return ToolResult(
                call_id=tool_call.id,
                output=f"Unknown shell_id: {shell_id}. Available: {available}",
            )
        return shell

    def _argument(self, tool_call: ToolCall, name: str) -> object:
        if not isinstance(tool_call.arguments, dict):
            return None
        return tool_call.arguments.get(name)

    def _extract_timeout_seconds(self, arguments: object) -> float | None:
        if not isinstance(arguments, dict):
            return None
        raw_timeout = arguments.get("timeout")
        if raw_timeout is None:
            return None
        if not isinstance(raw_timeout, (int, float)):
            raise ValueError("shell.exec timeout must be a number when provided.")
        if raw_timeout <= 0:
            raise ValueError("shell.exec timeout must be greater than 0.")
        return raw_timeout / 1000.0

    def _extract_workdir(self, arguments: object) -> str | None:
        if not isinstance(arguments, dict):
            return None
        workdir = arguments.get("workdir")
        if workdir is None:
            return None
        if not isinstance(workdir, str):
            raise ValueError("shell.exec workdir must be a string when provided.")
        return workdir

    def handle_exec(self, tool_call: ToolCall) -> ToolResult:
        shell = self._shell(tool_call)
        if isinstance(shell, ToolResult):
            return shell
        command = Tool.extract_cmd(tool_call.arguments)
        timeout_seconds = self._extract_timeout_seconds(tool_call.arguments)
        workdir = self._extract_workdir(tool_call.arguments)
        exec_arguments = {}
        if timeout_seconds is not None:
            exec_arguments["timeout_seconds"] = timeout_seconds
        if workdir is not None:
            exec_arguments["workdir"] = workdir
        output = shell.naive_exec(command, **exec_arguments)
        return ToolResult(call_id=tool_call.id, output=output)

    def handle_download(self, tool_call: ToolCall) -> ToolResult:
        shell = self._shell(tool_call)
        if isinstance(shell, ToolResult):
            return shell
        url = self._argument(tool_call, "url") or ""
        filepath = self._argument(tool_call, "filepath") or ""
        script = (
            'filepath="$2"; mkdir -p "$(dirname "$filepath")" && '
            'err=$(curl -sSLf -o "$filepath" "$1" 2>&1) && echo OK || '
            'echo "FAIL: $err"'
        )
        output = shell.naive_exec(["bash", "-c", script, "--", url, filepath]).strip()
        return ToolResult(call_id=tool_call.id, output=output)

    def handle_open_image(self, tool_call: ToolCall) -> ToolResult:
        shell = self._shell(tool_call)
        if isinstance(shell, ToolResult):
            return shell
        path = self._argument(tool_call, "path") or ""
        if not isinstance(path, str) or not path.strip():
            return ToolResult(
                call_id=tool_call.id,
                output="Missing required argument: 'path'",
            )
        python_code = (
            "import base64, sys;"
            "from PIL import Image;"
            "path = sys.argv[1];"
            "img = Image.open(path);"
            "print(Image.MIME.get(img.format, '') + ':' + base64.b64encode(open(path, 'rb').read()).decode())"
        )
        result = shell.subprocess_exec(["python", "-c", python_code, path])
        if result.returncode != 0:
            error_text = result.stderr.strip()
            if "FileNotFoundError" in error_text or "No such file" in error_text:
                return ToolResult(
                    call_id=tool_call.id,
                    output=f"File not found: {path}",
                )
            return ToolResult(
                call_id=tool_call.id,
                output=f"Unable to read image at path: {path}",
            )
        output_line = result.stdout.strip()
        mime, image_data = output_line.split(":", 1)
        allowed_mimes = {
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
        }
        if mime not in allowed_mimes:
            return ToolResult(
                call_id=tool_call.id,
                output=f"Unsupported image MIME type for path: {path}. Got: {mime}",
            )
        output = [MessageContentImage(image_url=f"data:{mime};base64,{image_data}")]
        return ToolResult(call_id=tool_call.id, output=output)


AGENTIC_TOOL = ShellTool
