from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictInt, TypeAdapter, model_validator

from app.commands.parser import (
    MediaControlIntent,
    OpenPlatformIntent,
    ParsedIntent,
    SearchMediaIntent,
    VolumeControlIntent,
    _clean_query,
)
from app.media.actions import MediaAction
from app.schemas.ws import Platform, SearchablePlatform


class LocalOpenPlatformIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent: Literal["OPEN_PLATFORM"]
    platform: Platform


class LocalSearchMediaIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    intent: Literal["SEARCH_MEDIA"]
    platform: SearchablePlatform
    query: str = Field(min_length=1, max_length=200)


class LocalMediaControlIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent: Literal["MEDIA_CONTROL"]
    action: MediaAction


class LocalVolumeIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent: Literal["SYSTEM_VOLUME"]
    action: Literal[
        "SYSTEM_VOLUME_SET",
        "SYSTEM_VOLUME_DELTA",
        "SYSTEM_MUTE_TOGGLE",
    ]
    level: StrictInt | None = Field(default=None, ge=0, le=100)
    delta: Literal[-5, 5] | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "LocalVolumeIntent":
        valid = (
            (self.action == "SYSTEM_VOLUME_SET" and self.level is not None and self.delta is None)
            or (self.action == "SYSTEM_VOLUME_DELTA" and self.delta is not None and self.level is None)
            or (self.action == "SYSTEM_MUTE_TOGGLE" and self.level is None and self.delta is None)
        )
        if not valid:
            raise ValueError("Volume action payload does not match its closed action.")
        return self


class LocalUnknownIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent: Literal["UNKNOWN"]


LocalIntent: TypeAlias = Annotated[
    LocalOpenPlatformIntent
    | LocalSearchMediaIntent
    | LocalMediaControlIntent
    | LocalVolumeIntent
    | LocalUnknownIntent,
    Field(discriminator="intent"),
]

_LOCAL_INTENT_ADAPTER = TypeAdapter(LocalIntent)


def parse_local_intent(payload: object) -> LocalIntent:
    return _LOCAL_INTENT_ADAPTER.validate_python(payload)


def local_intent_json_schema() -> dict:
    return _LOCAL_INTENT_ADAPTER.json_schema()


def to_parsed_intent(intent: LocalIntent) -> ParsedIntent:
    if isinstance(intent, LocalOpenPlatformIntent):
        return OpenPlatformIntent(type="OPEN_PLATFORM", platform=intent.platform)
    if isinstance(intent, LocalSearchMediaIntent):
        query = _clean_query(intent.query)
        if query is None:
            raise ValueError("Unsafe or empty search query.")
        return SearchMediaIntent(type="SEARCH_MEDIA", platform=intent.platform, query=query)
    if isinstance(intent, LocalMediaControlIntent):
        return MediaControlIntent(action=intent.action)
    if isinstance(intent, LocalVolumeIntent):
        return VolumeControlIntent(
            action=intent.action,
            level=intent.level,
            delta=intent.delta,
        )
    raise ValueError("The local model abstained.")
