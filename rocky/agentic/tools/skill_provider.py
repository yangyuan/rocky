from __future__ import annotations

import logging
from pathlib import Path
from zipfile import Path as ZipPath
from zipfile import BadZipFile, ZipFile

from rocky.agentic.contracts.skill import Skill, SkillSource

logger = logging.getLogger(__name__)


class SkillProvider:
    def __init__(self, *, skill_path: str, source: SkillSource):
        self._skill_path = Path(skill_path)
        self._source = source
        self._skill: Skill | None = None

    @property
    def skill(self) -> Skill:
        skill = self.provide()
        if skill is None:
            raise RuntimeError("Skill provider has no valid skill metadata.")
        return skill

    def provide(self) -> Skill | None:
        if self._skill is not None:
            return self._skill
        skill_file = self._skill_file_label()
        content = self._read_skill_content()
        if content is None:
            return None
        frontmatter_values = self._frontmatter_values(skill_file, content)
        if frontmatter_values is None:
            return None
        name = frontmatter_values.get("name")
        if name is None or not name.strip():
            logger.error("Ignoring skill without frontmatter name: %s", skill_file)
            return None
        name = name.strip()
        if name != self._skill_name():
            logger.error("Ignoring skill with name/path mismatch: %s", skill_file)
            return None
        description = frontmatter_values.get("description")
        if description is None or not description.strip():
            logger.error("Ignoring skill without description: %s", skill_file)
            return None
        description = description.strip()
        self._skill = Skill(
            id=f"{self._source.value}:{name}",
            name=name,
            description=description,
            source=self._source,
            path=str(self._skill_path),
        )
        return self._skill

    def read(self, path: str | None = None) -> str:
        normalized_path = self._normalized_read_path(path)
        if self._skill_path.is_dir():
            return self._read_folder_path(normalized_path)
        if self._skill_path.is_file() and self._skill_path.suffix.lower() == ".zip":
            return self._read_zip_path(normalized_path)
        return self._read_error(
            f"Unsupported skill path: {self._skill_path}",
            self._directory_structure(),
        )

    def _skill_name(self) -> str:
        if self._skill_path.is_file() and self._skill_path.suffix.lower() == ".zip":
            return self._skill_path.stem
        return self._skill_path.name

    def _skill_file_label(self) -> str:
        if self._skill_path.is_file() and self._skill_path.suffix.lower() == ".zip":
            return f"{self._skill_path}!SKILL.md"
        return str(self._skill_path / "SKILL.md")

    def _read_skill_content(self) -> str | None:
        if self._skill_path.is_dir():
            return self._read_folder_skill_content()
        if self._skill_path.is_file() and self._skill_path.suffix.lower() == ".zip":
            return self._read_zip_skill_content()
        logger.error("Ignoring unsupported skill path: %s", self._skill_path)
        return None

    def _read_folder_skill_content(self) -> str | None:
        skill_file = self._skill_path / "SKILL.md"
        if not skill_file.is_file():
            logger.error("Ignoring skill without SKILL.md: %s", self._skill_path)
            return None
        try:
            return skill_file.read_text(encoding="utf-8")
        except OSError:
            logger.exception("Ignoring unreadable skill: %s", self._skill_path)
            return None

    def _read_zip_skill_content(self) -> str | None:
        try:
            with ZipFile(self._skill_path) as archive:
                try:
                    raw = archive.read("SKILL.md")
                except KeyError:
                    logger.error(
                        "Ignoring skill zip without SKILL.md: %s", self._skill_path
                    )
                    return None
        except (BadZipFile, OSError):
            logger.exception("Ignoring unreadable skill zip: %s", self._skill_path)
            return None
        return raw.decode("utf-8", errors="replace")

    def _normalized_read_path(self, path: str | None) -> str:
        if path is None:
            return "SKILL.md"
        normalized = path.strip().replace("\\", "/")
        if not normalized or normalized == ".":
            return "SKILL.md"
        return normalized

    def _read_folder_path(self, path: str) -> str:
        structure = self._folder_structure()
        if not self._is_relative_path(path):
            return self._read_error(f"Invalid skill path: {path}", structure)
        target = self._skill_path / path
        try:
            target = target.resolve()
            root = self._skill_path.resolve()
        except OSError:
            return self._read_error(f"File or folder not found: {path}", structure)
        if root not in [target, *target.parents]:
            return self._read_error(f"Invalid skill path: {path}", structure)
        if not target.exists():
            return self._read_error(f"File or folder not found: {path}", structure)
        if target.is_dir():
            return structure
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._read_error(f"Skill file is not text: {path}", structure)
        except OSError:
            return self._read_error(f"Unable to read skill file: {path}", structure)
        return self._read_output(structure, path, content)

    def _read_zip_path(self, path: str) -> str:
        structure = self._zip_structure()
        if not self._is_relative_path(path):
            return self._read_error(f"Invalid skill path: {path}", structure)
        try:
            with ZipFile(self._skill_path) as archive:
                archive_path = ZipPath(archive, path)
                if not archive_path.exists():
                    return self._read_error(
                        f"File or folder not found: {path}", structure
                    )
                if archive_path.is_dir():
                    return structure
                try:
                    content = archive_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    return self._read_error(
                        f"Skill file is not text: {path}", structure
                    )
                except OSError:
                    return self._read_error(
                        f"Unable to read skill file: {path}", structure
                    )
        except (BadZipFile, OSError):
            logger.exception("Unable to inspect skill zip: %s", self._skill_path)
            return self._read_error(
                f"Unable to inspect skill zip: {self._skill_path}", structure
            )
        return self._read_output(structure, path, content)

    def _directory_structure(self) -> str:
        if self._skill_path.is_dir():
            return self._folder_structure()
        if self._skill_path.is_file() and self._skill_path.suffix.lower() == ".zip":
            return self._zip_structure()
        return ""

    def _folder_structure(self) -> str:
        lines: list[str] = [f"{self._skill_name()}/"]
        try:
            paths = sorted(
                self._skill_path.rglob("*"), key=lambda item: item.as_posix().lower()
            )
        except OSError:
            return lines[0]
        for path in paths:
            relative = path.relative_to(self._skill_path).as_posix()
            lines.append(f"{relative}/" if path.is_dir() else relative)
        return "\n".join(lines)

    def _zip_structure(self) -> str:
        lines: list[str] = [f"{self._skill_name()}.zip"]
        try:
            with ZipFile(self._skill_path) as archive:
                names = sorted(
                    (name for name in archive.namelist() if name), key=str.lower
                )
        except (BadZipFile, OSError):
            logger.exception("Unable to inspect skill zip: %s", self._skill_path)
            return lines[0]
        lines.extend(names)
        return "\n".join(lines)

    def _read_output(self, structure: str, path: str, content: str) -> str:
        return "Directory structure:\n" f"{structure}\n\n" f"{path}:\n" f"{content}"

    def _read_error(self, error: str, structure: str) -> str:
        return f"Error: {error}\n\nDirectory structure:\n{structure}"

    def _is_relative_path(self, path: str) -> bool:
        parsed = Path(path)
        parts = parsed.parts
        return (
            bool(path)
            and not path.startswith("/")
            and not parsed.drive
            and not parsed.is_absolute()
            and ".." not in parts
        )

    def _frontmatter_values(
        self, skill_file: str, content: str
    ) -> dict[str, str] | None:
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            logger.error("Ignoring skill without frontmatter: %s", skill_file)
            return None
        closing_index: int | None = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                closing_index = index
                break
        if closing_index is None:
            logger.error("Ignoring skill with unclosed frontmatter: %s", skill_file)
            return None
        values: dict[str, str] = {}
        for line in lines[1:closing_index]:
            if ":" not in line:
                logger.error("Ignoring skill with invalid frontmatter: %s", skill_file)
                return None
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key or not value:
                logger.error("Ignoring skill with invalid frontmatter: %s", skill_file)
                return None
            values[key] = value
        return values
