ROCKY_RUNTIME_DEVELOPER_MESSAGE_TEMPLATE = """
Rocky runtime state:
{RUNTIME_STATE}

This is the latest snapshot of tools and environments available to you. When invoking shell tools, set `shell_id` to one of the listed environment ids; do not invent ids. If a later runtime state is provided, trust the most recent one and ignore earlier states.
""".strip()
