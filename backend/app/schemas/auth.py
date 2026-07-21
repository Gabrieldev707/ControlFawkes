from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AuthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    deviceId: str = Field(min_length=1, max_length=128)
    token: str = Field(min_length=16, max_length=512)


class PairDevicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pin: str = Field(pattern=r"^\d{6}$")
    deviceName: str = Field(min_length=1, max_length=80)


class AuthMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["AUTH"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: AuthPayload


class PairDeviceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["PAIR_DEVICE"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: PairDevicePayload


class AuthResultMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1] = 1
    type: Literal["AUTH_RESULT"] = "AUTH_RESULT"
    requestId: str
    success: Literal[True] = True
    message: str


class PairResultMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1] = 1
    type: Literal["PAIR_RESULT"] = "PAIR_RESULT"
    requestId: str
    success: Literal[True] = True
    message: str
    deviceId: str
    token: str
