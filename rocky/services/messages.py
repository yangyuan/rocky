from __future__ import annotations

import json
import logging
from typing import Optional

from pydantic import BaseModel

from rocky.contracts.chat import (
    RockyChatContent,
    RockyChatContentPart,
    RockyChatContentPartType,
    RockyChatFileContentPart,
    RockyChatImageDetail,
    RockyChatImageContentPart,
    RockyChatTextContentPart,
    RockyJsonValue,
)

logger = logging.getLogger(__name__)


class RockyMessages:
    @staticmethod
    def to_json_value(value: object) -> RockyJsonValue:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {
                str(key): RockyMessages.to_json_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [RockyMessages.to_json_value(item) for item in value]
        if isinstance(value, BaseModel):
            return RockyMessages.to_json_value(value.model_dump(exclude_unset=True))
        return str(value)

    @staticmethod
    def tool_result_to_chat_content(
        output: RockyJsonValue,
    ) -> RockyChatContent:
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        if isinstance(output, list):
            content_parts = RockyMessages._content_parts(output)
            return (
                content_parts
                if content_parts is not None
                else RockyMessages._json_text(output)
            )
        if isinstance(output, dict):
            content_parts = RockyMessages._content_parts([output])
            return (
                content_parts
                if content_parts is not None
                else RockyMessages._json_text(output)
            )
        return RockyMessages._json_text(output)

    @staticmethod
    def _content_parts(
        value: list[RockyJsonValue],
    ) -> Optional[list[RockyChatContentPart]]:
        parts: list[RockyChatContentPart] = []
        for item in value:
            if isinstance(item, dict):
                part = RockyMessages._content_part(item)
                if part is None:
                    return None
                parts.append(part)
            else:
                return None
        return parts

    @staticmethod
    def _content_part(
        value: dict[str, RockyJsonValue],
    ) -> Optional[RockyChatContentPart]:
        content_type = value.get("type")
        match content_type:
            case RockyChatContentPartType.TEXT | "input_text" | "output_text":
                text = value.get("text")
                return (
                    RockyChatTextContentPart(text=text)
                    if isinstance(text, str)
                    else None
                )
            case RockyChatContentPartType.IMAGE | "input_image" | "image_url":
                image_url = RockyMessages._image_url(value)
                detail = value.get("detail")
                return (
                    RockyChatImageContentPart(
                        image_url=image_url,
                        detail=(
                            RockyChatImageDetail(detail)
                            if detail in RockyChatImageDetail
                            else RockyChatImageDetail.AUTO
                        ),
                    )
                    if image_url is not None
                    else None
                )
            case RockyChatContentPartType.FILE | "input_file":
                return RockyMessages._file_content_part(value)
            case _:
                if "type" in value:
                    logger.warning(
                        "Unsupported chat content part type: %s", content_type
                    )
                return None

    @staticmethod
    def _json_text(value: RockyJsonValue) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _image_url(value: dict[str, RockyJsonValue]) -> Optional[str]:
        image_url = value.get("image_url")
        if isinstance(image_url, dict):
            image_url = image_url.get("url")
        return image_url if isinstance(image_url, str) else None

    @staticmethod
    def _file_content_part(
        value: dict[str, RockyJsonValue],
    ) -> Optional[RockyChatFileContentPart]:
        file_data = value.get("file_data")
        filename = value.get("filename")
        if not isinstance(file_data, str):
            return None
        return RockyChatFileContentPart(
            file_data=file_data,
            filename=filename if isinstance(filename, str) else None,
        )
