from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import AuthMessage, PairDeviceMessage


ProtocolVersion = Literal[1]
Platform = Literal[
    "NETFLIX",
    "MAX",
    "PRIME_VIDEO",
    "DISNEY_PLUS",
    "YOUTUBE",
    "SPOTIFY",
]
ServerState = Literal["AUTH_REQUIRED", "PAIRING", "READY", "BUSY"]
ErrorCode = Literal[
    "INVALID_JSON",
    "INVALID_PAYLOAD",
    "UNSUPPORTED_MESSAGE",
    "NOT_IMPLEMENTED",
    "UNKNOWN_COMMAND",
    "UNAUTHORIZED",
    "INVALID_TOKEN",
    "PAIRING_REQUIRED",
    "PIN_INVALID",
    "PIN_EXPIRED",
    "TOO_MANY_ATTEMPTS",
    "PROTOCOL_VERSION_MISMATCH",
    "PLATFORM_OPEN_FAILED",
    "INTERNAL_ERROR",
]


class PlatformSelectedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform


class TextCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)


class PlatformSelectedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion
    type: Literal["PLATFORM_SELECTED"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: PlatformSelectedPayload


class TextCommandMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion
    type: Literal["TEXT_COMMAND"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: TextCommandPayload


ClientMessage = Annotated[
    AuthMessage | PairDeviceMessage | PlatformSelectedMessage | TextCommandMessage,
    Field(discriminator="type"),
]


class StateUpdateMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["STATE_UPDATE"] = "STATE_UPDATE"
    state: ServerState
    message: str


class PlatformCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["OPEN_PLATFORM"] = "OPEN_PLATFORM"
    platform: Platform
    executed: bool = False


class HelpCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SHOW_HELP"] = "SHOW_HELP"
    commands: list[str]
    executed: Literal[False] = False


class CommandResultMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["COMMAND_RESULT"] = "COMMAND_RESULT"
    requestId: str
    success: Literal[True] = True
    message: str
    data: PlatformCommandData | HelpCommandData


class ErrorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["ERROR"] = "ERROR"
    requestId: str
    code: ErrorCode
    message: str
