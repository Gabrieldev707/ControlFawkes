from typing import Literal, TypeAlias

import unicodedata

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.input.keyboard import SafeKey


KeyboardAction: TypeAlias = Literal["KEYBOARD_TEXT", "KEYBOARD_KEY"]
KEYBOARD_ACTIONS: tuple[KeyboardAction, ...] = ("KEYBOARD_TEXT", "KEYBOARD_KEY")


class KeyboardTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: StrictStr = Field(min_length=1, max_length=256)

    @field_validator("text")
    @classmethod
    def reject_empty_or_control_characters(cls, value: str) -> str:
        if not value.strip() or any(
            unicodedata.category(character) in {"Cc", "Cs"}
            for character in value
        ):
            raise ValueError("text contains unsupported characters")
        return value


class KeyboardKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: SafeKey


class KeyboardTextMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["KEYBOARD_TEXT"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: KeyboardTextPayload


class KeyboardKeyMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["KEYBOARD_KEY"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: KeyboardKeyPayload
