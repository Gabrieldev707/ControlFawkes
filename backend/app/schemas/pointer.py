from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


PointerAction: TypeAlias = Literal[
    "POINTER_MOVE",
    "POINTER_CLICK",
    "POINTER_DOUBLE_CLICK",
    "POINTER_RIGHT_CLICK",
    "POINTER_SCROLL",
    "POINTER_DOWN",
    "POINTER_UP",
]

POINTER_ACTIONS: tuple[PointerAction, ...] = (
    "POINTER_MOVE",
    "POINTER_CLICK",
    "POINTER_DOUBLE_CLICK",
    "POINTER_RIGHT_CLICK",
    "POINTER_SCROLL",
    "POINTER_DOWN",
    "POINTER_UP",
)

PointerDelta = Annotated[float, Field(strict=True, ge=-160, le=160, allow_inf_nan=False)]


class PointerMovePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dx: PointerDelta
    dy: PointerDelta

    @model_validator(mode="after")
    def require_movement(self) -> "PointerMovePayload":
        if self.dx == 0 and self.dy == 0:
            raise ValueError("movement cannot be zero")
        return self


class PointerScrollPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delta: Literal[-120, 120]


class PointerMoveMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["POINTER_MOVE"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: PointerMovePayload


class PointerScrollMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["POINTER_SCROLL"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: PointerScrollPayload


class PointerClickMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["POINTER_CLICK"]
    requestId: str = Field(min_length=1, max_length=128)


class PointerDoubleClickMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["POINTER_DOUBLE_CLICK"]
    requestId: str = Field(min_length=1, max_length=128)


class PointerRightClickMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["POINTER_RIGHT_CLICK"]
    requestId: str = Field(min_length=1, max_length=128)


class PointerDownMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["POINTER_DOWN"]
    requestId: str = Field(min_length=1, max_length=128)


class PointerUpMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["POINTER_UP"]
    requestId: str = Field(min_length=1, max_length=128)
