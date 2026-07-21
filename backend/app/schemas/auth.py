from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

# Client -> Server
class PairDevicePayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pin: str = Field(..., min_length=6, max_length=6)
    deviceName: str = Field(..., min_length=1, max_length=100)

class AuthPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    deviceId: str = Field(..., min_length=1, max_length=64)
    token: str = Field(..., min_length=1, max_length=64)

class PairDeviceMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['PAIR_DEVICE']
    requestId: str = Field(..., min_length=1, max_length=64)
    payload: PairDevicePayload

class AuthMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['AUTH']
    requestId: str = Field(..., min_length=1, max_length=64)
    payload: AuthPayload

# Server -> Client
class AuthRequiredMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['AUTH_REQUIRED'] = 'AUTH_REQUIRED'
    # No requestId since it's unprompted

class AuthResultMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['AUTH_RESULT'] = 'AUTH_RESULT'
    requestId: str
    success: bool
    deviceId: Optional[str] = None
    message: str

class PairResultMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['PAIR_RESULT'] = 'PAIR_RESULT'
    requestId: str
    success: bool
    deviceId: Optional[str] = None
    token: Optional[str] = None
    message: str
