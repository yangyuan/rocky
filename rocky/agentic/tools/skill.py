from __future__ import annotations

from rocky.agentic.contracts.skill import Skill
from rocky.agentic.contracts.tools import (
    FunctionDefinition,
    JsonSchema,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from rocky.agentic.tools.skill_provider import SkillProvider
from rocky.agentic.tools.tool import Tool

SKILL_READ_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "The enabled skill name or id to read. Leave empty only when exactly one skill is enabled.",
            "default": "",
        },
        "path": {
            "type": ["string", "null"],
            "description": "A relative path inside the skill. Empty, null, or SKILL.md reads the skill manifest.",
            "default": None,
        },
    },
}

SKILL_TOOL_DEFINITION = ToolDefinition(
    name="skill",
    description="Read enabled skill files without assuming anything from skill metadata.",
    channel="commentary",
    unconstrained=True,
    functions=[
        FunctionDefinition(
            name="read",
            description="Read an enabled skill's SKILL.md or another relative file/folder path inside the skill.",
            parameters=JsonSchema.model_validate(SKILL_READ_SCHEMA),
            strict=False,
        )
    ],
)


class SkillTool(Tool):
    def __init__(self, skills: list[Skill]) -> None:
        super().__init__("skill")
        self.skills = list(skills)
        self.providers_by_id: dict[str, SkillProvider] = {}
        self.providers_by_name: dict[str, list[SkillProvider]] = {}
        for skill in self.skills:
            provider = SkillProvider(skill_path=skill.path, source=skill.source)
            self.providers_by_id[skill.id] = provider
            providers = self.providers_by_name.get(skill.name, [])
            self.providers_by_name[skill.name] = providers + [provider]
        self.register_callback("read", self.handle_read)

    def get_tool_definition(self) -> ToolDefinition:
        return SKILL_TOOL_DEFINITION

    def handle_read(self, tool_call: ToolCall) -> ToolResult:
        if not isinstance(tool_call.arguments, dict):
            return ToolResult(
                call_id=tool_call.id,
                output="skill.read arguments must be an object.",
            )
        provider = self._provider(tool_call.id, tool_call.arguments.get("name"))
        if isinstance(provider, ToolResult):
            return provider
        path = tool_call.arguments.get("path")
        if path is not None and not isinstance(path, str):
            return ToolResult(
                call_id=tool_call.id,
                output="skill.read path must be a string, null, or omitted.",
            )
        return ToolResult(call_id=tool_call.id, output=provider.read(path))

    def _provider(self, call_id: str, name: object) -> SkillProvider | ToolResult:
        if isinstance(name, str) and name.strip():
            normalized_name = name.strip()
            provider = self.providers_by_id.get(normalized_name)
            if provider is not None:
                return provider
            providers = self.providers_by_name.get(normalized_name, [])
            if len(providers) == 1:
                return providers[0]
            if len(providers) > 1:
                matching_ids = [
                    skill.id for skill in self.skills if skill.name == normalized_name
                ]
                return ToolResult(
                    call_id=call_id,
                    output=(
                        f"Ambiguous skill name: {normalized_name}. "
                        f"Use one of these ids: {', '.join(matching_ids)}"
                    ),
                )
            available = ", ".join(sorted(self.providers_by_id)) or "none"
            return ToolResult(
                call_id=call_id,
                output=f"Unknown skill name: {name}. Available: {available}",
            )
        if len(self.providers_by_id) == 1:
            return next(iter(self.providers_by_id.values()))
        available = ", ".join(sorted(self.providers_by_id)) or "none"
        return ToolResult(
            call_id=call_id,
            output=f"Missing required skill name. Available: {available}",
        )
