from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel


class MessageContentText(BaseModel):
    type: Literal["text"] = "text"
    text: str


class MessageContentImage(BaseModel):
    type: Literal["image"] = "image"
    image_url: str


MessageContent = Union[MessageContentText, MessageContentImage]
