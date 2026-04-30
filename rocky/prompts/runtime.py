ROCKY_RUNTIME_DEVELOPER_MESSAGE_TEMPLATE = """
Use only the latest Rocky runtime state.

Runtime state usually contains
- Shell environments that are available for executing commands.
  When invoking shell tools, set `shell_id` to one of the listed environment ids. Do not invent ids.
  Local shell environments have `kind: "local"` and an `os` value. Their `cmd` arrays run directly in the chat workspace with no implicit shell. Choose the executable for that OS; for shell built-ins, pipelines, or shell syntax, include the shell explicitly, such as `cmd.exe` on Windows, `zsh` on macOS, or `sh` on Linux.
- Enabled skills that are available for use.
  Enabled skills are listed with their id, name, description, and source. Use that basic skill information to decide when a skill is relevant.

Rocky runtime state:
{RUNTIME_STATE}
""".strip()
