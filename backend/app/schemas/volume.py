from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, StrictInt

# Client -> Server

class VolumeGetPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pass

class VolumeSetPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # StrictInt rejects floats, booleans, strings
    level: StrictInt = Field(..., ge=0, le=100)

class VolumeStepPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    delta: Literal[-5, 5]

class VolumeToggleMutePayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pass

class VolumeGetMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['VOLUME_GET']
    requestId: str = Field(..., min_length=1, max_length=64)
    payload: VolumeGetPayload

class VolumeSetMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['VOLUME_SET']
    requestId: str = Field(..., min_length=1, max_length=64)
    payload: VolumeSetPayload

class VolumeStepMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['VOLUME_STEP']
    requestId: str = Field(..., min_length=1, max_length=64)
    payload: VolumeStepPayload

class VolumeToggleMuteMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['VOLUME_TOGGLE_MUTE']
    requestId: str = Field(..., min_length=1, max_length=64)
    payload: VolumeToggleMutePayload

# Server -> Client
class VolumeStateMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['VOLUME_STATE'] = 'VOLUME_STATE'
    requestId: str
    level: StrictInt
    muted: bool
