from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.schemas.auth import AuthMessage, PairDeviceMessage
from app.media.actions import MediaAction
from app.schemas.volume import (
    VolumeAction,
    VolumeDeltaMessage,
    VolumeGetMessage,
    VolumeMuteToggleMessage,
    VolumeSetMessage,
)
from app.schemas.pointer import (
    PointerAction,
    PointerClickMessage,
    PointerDoubleClickMessage,
    PointerDownMessage,
    PointerMoveMessage,
    PointerRightClickMessage,
    PointerScrollMessage,
    PointerUpMessage,
)
from app.schemas.keyboard import KeyboardAction, KeyboardKeyMessage, KeyboardTextMessage


ProtocolVersion = Literal[1]
Platform = Literal[
    "NETFLIX",
    "MAX",
    "PRIME_VIDEO",
    "DISNEY_PLUS",
    "YOUTUBE",
    "SPOTIFY",
]
LaunchStrategy = Literal["CHROME", "SPOTIFY_APP", "SPOTIFY_WEB_CHROME"]
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
    "MEDIA_SEARCH_FAILED",
    "MEDIA_CONTROL_FAILED",
    "MEDIA_SESSION_NOT_FOUND",
    "MEDIA_ACTION_UNSUPPORTED",
    "SYSTEM_VOLUME_FAILED",
    "POINTER_CONTROL_FAILED",
    "POINTER_RATE_LIMITED",
    "RATE_LIMITED",
    "KEYBOARD_CONTROL_FAILED",
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


class MediaControlMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion
    type: MediaAction
    requestId: str = Field(min_length=1, max_length=128)


ClientMessage = Annotated[
    AuthMessage
    | PairDeviceMessage
    | PlatformSelectedMessage
    | TextCommandMessage
    | MediaControlMessage
    | VolumeGetMessage
    | VolumeSetMessage
    | VolumeDeltaMessage
    | VolumeMuteToggleMessage
    | PointerMoveMessage
    | PointerClickMessage
    | PointerDoubleClickMessage
    | PointerRightClickMessage
    | PointerScrollMessage
    | PointerDownMessage
    | PointerUpMessage
    | KeyboardTextMessage
    | KeyboardKeyMessage,
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
    executed: Literal[True] = True
    strategy: LaunchStrategy


class SearchMediaCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SEARCH_MEDIA"] = "SEARCH_MEDIA"
    platform: Literal["YOUTUBE", "SPOTIFY"]
    executed: Literal[True] = True
    strategy: LaunchStrategy


class HelpCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SHOW_HELP"] = "SHOW_HELP"
    commands: list[str]
    executed: Literal[False] = False


class MediaCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["MEDIA_CONTROL"] = "MEDIA_CONTROL"
    action: MediaAction
    platform: Platform
    session: Literal["WEB", "APP"]
    executed: Literal[True] = True


class VolumeCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SYSTEM_VOLUME"] = "SYSTEM_VOLUME"
    action: VolumeAction
    level: StrictInt = Field(ge=0, le=100)
    muted: bool
    executed: Literal[True] = True


class PointerCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["POINTER_CONTROL"] = "POINTER_CONTROL"
    action: PointerAction
    executed: Literal[True] = True


class KeyboardCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["KEYBOARD_CONTROL"] = "KEYBOARD_CONTROL"
    action: KeyboardAction
    executed: Literal[True] = True


class CommandResultMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["COMMAND_RESULT"] = "COMMAND_RESULT"
    requestId: str
    success: Literal[True] = True
    message: str
    data: (
        PlatformCommandData
        | SearchMediaCommandData
        | HelpCommandData
        | MediaCommandData
        | VolumeCommandData
        | PointerCommandData
        | KeyboardCommandData
    )


class ErrorMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: ProtocolVersion = 1
    type: Literal["ERROR"] = "ERROR"
    requestId: str
    code: ErrorCode
    message: str
