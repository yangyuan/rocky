from enum import StrEnum
import ntpath
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

_WIN_COMMAND_LINE_LIMIT = 32_000


class ShellType(StrEnum):
    LOCAL = "local"
    DOCKER = "docker"
    DOCKER_IN_WSL = "docker_in_wsl"
    DOCKER_OVER_SSH = "docker_over_ssh"
    SSH = "ssh"
    WSL = "wsl"


class ShellProvider:
    def __init__(
        self,
        shell_name: str = "",
        shell_type: ShellType = ShellType.DOCKER,
        shell_host: str | None = None,
        local_workdir: str | None = None,
        output_max_head_tail: Optional[int] = None,
    ):
        self.name = shell_name
        self.shell_type = shell_type
        self.host = shell_host
        self.local_workdir = local_workdir
        self.output_max_head_tail = output_max_head_tail

    @property
    def is_local(self) -> bool:
        return self.shell_type == ShellType.LOCAL

    @staticmethod
    def local_os() -> str:
        if sys.platform == "win32":
            return "windows"
        if sys.platform == "darwin":
            return "macos"
        return "linux"

    @staticmethod
    def build_python_exec_command(script: str, executable: str = "python") -> list[str]:
        displayhook_name = "__agentic_python_runner__"
        runner_filename = "<agentic-python-runner>"
        wrapper = f"""
import ast
import sys

source = sys.argv[1]
sys.argv = ['-c']
tree = ast.parse(source, filename={runner_filename!r}, mode='exec')
displayhook = sys.displayhook
body = []

for index, node in enumerate(tree.body):
    is_module_docstring = (
        index == 0
        and isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )
    if is_module_docstring:
        body.append(node)
        continue

    if isinstance(node, ast.Expr):
        call = ast.Call(
            func=ast.Name(id={displayhook_name!r}, ctx=ast.Load()),
            args=[node.value],
            keywords=[],
        )
        body.append(ast.copy_location(ast.Expr(value=call), node))
        continue

    body.append(node)

tree.body = body
ast.fix_missing_locations(tree)
namespace = {{
    '__name__': '__main__',
    '__builtins__': __builtins__,
    {displayhook_name!r}: displayhook,
}}
exec(compile(tree, {runner_filename!r}, 'exec'), namespace, namespace)
""".strip()
        return [executable, "-c", wrapper, script]

    async def initialize(self) -> None:
        if self.is_local and self.local_workdir is not None:
            Path(self.local_workdir).mkdir(parents=True, exist_ok=True)

    def _is_command_too_long(self, full_command: list[str]) -> bool:
        if sys.platform != "win32":
            return False
        return len(subprocess.list2cmdline(full_command)) > _WIN_COMMAND_LINE_LIMIT

    def _build_stdin_script(self, command: list[str]) -> str:
        return " ".join(shlex.quote(part) for part in command) + "\n"

    def _validate_linux_workdir(self, workdir: str | None) -> str | None:
        if workdir is None:
            return None
        if not isinstance(workdir, str):
            raise ValueError("shell.exec workdir must be a string when provided.")
        if not workdir:
            raise ValueError("shell.exec workdir must not be empty.")
        if not workdir.startswith("/"):
            raise ValueError("shell.exec workdir must be an absolute Linux path.")
        return workdir

    def _validate_local_workdir(self, workdir: str | None) -> str | None:
        if workdir is None:
            if self.local_workdir is None:
                return None
            workdir = self.local_workdir
        if not isinstance(workdir, str):
            raise ValueError("shell.exec workdir must be a string when provided.")
        if not workdir:
            raise ValueError("shell.exec workdir must not be empty.")
        if sys.platform == "win32":
            if not ntpath.isabs(workdir):
                raise ValueError("shell.exec workdir must be an absolute Windows path.")
        elif not Path(workdir).is_absolute():
            raise ValueError("shell.exec workdir must be an absolute path.")
        return workdir

    def _wsl_command(self, command: list[str], workdir: str | None = None) -> list[str]:
        workdir_args = ["--cd", workdir] if workdir else []
        if self.host:
            return ["wsl", "-d", self.host, *workdir_args, "-e", *command]
        return ["wsl", *workdir_args, "-e", *command]

    def _ssh_command(self, command: list[str], workdir: str | None = None) -> list[str]:
        parts = " ".join(
            "\"$(printf '{}')\"".format(
                "".join(f"\\{byte:03o}" for byte in part.encode())
            )
            for part in command
        )
        remote_command = f"exec {parts}"
        if workdir:
            remote_command = f"cd -- {shlex.quote(workdir)} && {remote_command}"
        return [
            "ssh",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ServerAliveInterval=5",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            self.host,
            remote_command,
        ]

    def _docker_command(
        self, command: list[str], workdir: str | None = None
    ) -> list[str]:
        workdir_args = ["-w", workdir] if workdir else []
        return ["docker", "exec", *workdir_args, self.name, *command]

    def _docker_interactive_command(
        self, command: list[str], workdir: str | None = None
    ) -> list[str]:
        workdir_args = ["-w", workdir] if workdir else []
        return ["docker", "exec", "-i", *workdir_args, self.name, *command]

    def _shell_command(
        self, command: list[str], workdir: str | None = None
    ) -> list[str]:
        if self.shell_type == ShellType.LOCAL:
            return command
        workdir = self._validate_linux_workdir(workdir)
        if self.shell_type == ShellType.WSL:
            return self._wsl_command(command, workdir=workdir)
        if self.shell_type == ShellType.SSH:
            return self._ssh_command(command, workdir=workdir)
        if self.shell_type == ShellType.DOCKER_IN_WSL:
            return self._wsl_command(self._docker_command(command, workdir=workdir))
        if self.shell_type == ShellType.DOCKER_OVER_SSH:
            return self._ssh_command(self._docker_command(command, workdir=workdir))
        return self._docker_command(command, workdir=workdir)

    def _shell_interactive_command(
        self, command: list[str], workdir: str | None = None
    ) -> list[str]:
        if self.shell_type == ShellType.LOCAL:
            return command
        workdir = self._validate_linux_workdir(workdir)
        if self.shell_type == ShellType.WSL:
            return self._wsl_command(command, workdir=workdir)
        if self.shell_type == ShellType.SSH:
            return self._ssh_command(command, workdir=workdir)
        if self.shell_type == ShellType.DOCKER_IN_WSL:
            return self._wsl_command(
                self._docker_interactive_command(command, workdir=workdir)
            )
        if self.shell_type == ShellType.DOCKER_OVER_SSH:
            return self._ssh_command(
                self._docker_interactive_command(command, workdir=workdir)
            )
        return self._docker_interactive_command(command, workdir=workdir)

    def subprocess_exec(
        self,
        command: list[str],
        timeout_seconds: float = 120,
        workdir: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        full_command = self._shell_command(command, workdir=workdir)
        cwd = self._validate_local_workdir(workdir) if self.is_local else None
        try:
            if not self.is_local and self._is_command_too_long(full_command):
                stdin_command = self._shell_interactive_command(
                    ["sh", "-s"], workdir=workdir
                )
                script = self._build_stdin_script(command)
                result = subprocess.run(
                    stdin_command,
                    input=script,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=cwd,
                )
            else:
                result = subprocess.run(
                    full_command,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    stdin=subprocess.DEVNULL,
                    cwd=cwd,
                )
        except (subprocess.TimeoutExpired, OSError) as error:
            print(f"[Shell] exec failed: {error}")
            raise
        return result

    def naive_exec(
        self,
        command: list[str],
        timeout_seconds: float = 120,
        workdir: str | None = None,
    ) -> str:
        full_command = self._shell_command(command, workdir=workdir)
        cwd = self._validate_local_workdir(workdir) if self.is_local else None
        try:
            if not self.is_local and self._is_command_too_long(full_command):
                stdin_command = self._shell_interactive_command(
                    ["sh", "-s"], workdir=workdir
                )
                script = self._build_stdin_script(command)
                result = subprocess.run(
                    stdin_command,
                    input=script.encode(),
                    capture_output=True,
                    timeout=timeout_seconds,
                    cwd=cwd,
                )
            else:
                result = subprocess.run(
                    full_command,
                    capture_output=True,
                    timeout=timeout_seconds,
                    stdin=subprocess.DEVNULL,
                    cwd=cwd,
                )
        except (subprocess.TimeoutExpired, OSError) as error:
            print(f"[Shell] exec failed: {error}")
            raise
        output = result.stdout.decode("utf-8", errors="replace")
        if result.stderr:
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            if output:
                output += "\n"
            output += f"STDERR:\n{stderr_text}"
        if (
            self.output_max_head_tail is not None
            and len(output) > 2 * self.output_max_head_tail
        ):
            output = (
                output[: self.output_max_head_tail]
                + "[... ELLIPSIZATION ...]"
                + output[-self.output_max_head_tail :]
            )
        return output

    def _write_file(self, remote_path: str, data: bytes) -> None:
        if self.is_local:
            path = Path(remote_path)
            if not path.is_absolute():
                base = Path(self.local_workdir) if self.local_workdir else Path.cwd()
                path = base / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return
        command = self._shell_interactive_command(
            ["sh", "-c", f"cat > {shlex.quote(remote_path)}"]
        )
        try:
            result = subprocess.run(
                command, input=data, capture_output=True, timeout=1800
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            print(f"[Shell] write_file failed: {error}")
            raise
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            print(f"[Shell] write_file error: {stderr_text}")
            raise RuntimeError(stderr_text)

    def _read_file(self, remote_path: str) -> bytes:
        if self.is_local:
            path = Path(remote_path)
            if not path.is_absolute():
                base = Path(self.local_workdir) if self.local_workdir else Path.cwd()
                path = base / path
            return path.read_bytes()
        command = self._shell_command(["cat", remote_path])
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=1800,
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            print(f"[Shell] read_file failed: {error}")
            raise
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            print(f"[Shell] read_file error: {stderr_text}")
            raise RuntimeError(stderr_text)
        return result.stdout
