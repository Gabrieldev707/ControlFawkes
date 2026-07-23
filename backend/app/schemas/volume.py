from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictInt


VolumeAction: TypeAlias = Literal[
    "SYSTEM_VOLUME_GET",
    "SYSTEM_VOLUME_SET",
    "SYSTEM_VOLUME_DELTA",
    "SYSTEM_MUTE_TOGGLE",
]

VOLUME_ACTIONS: tuple[VolumeAction, ...] = (
    "SYSTEM_VOLUME_GET",
    "SYSTEM_VOLUME_SET",
    "SYSTEM_VOLUME_DELTA",
    "SYSTEM_MUTE_TOGGLE",
)


class VolumeSetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: StrictInt = Field(ge=0, le=100)


class VolumeDeltaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delta: Literal[-5, 5]


class VolumeGetMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["SYSTEM_VOLUME_GET"]
    requestId: str = Field(min_length=1, max_length=128)


class VolumeSetMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["SYSTEM_VOLUME_SET"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: VolumeSetPayload


class VolumeDeltaMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["SYSTEM_VOLUME_DELTA"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: VolumeDeltaPayload


class VolumeMuteToggleMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["SYSTEM_MUTE_TOGGLE"]
    requestId: str = Field(min_length=1, max_length=128)
