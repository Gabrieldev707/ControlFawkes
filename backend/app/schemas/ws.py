from typing import Any, Literal, Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.auth import (
    AuthMessage, PairDeviceMessage,
    AuthRequiredMessage, AuthResultMessage, PairResultMessage
)
from app.schemas.volume import (
    VolumeGetMessage, VolumeSetMessage, VolumeStepMessage, VolumeToggleMuteMessage,
    VolumeStateMessage
)

# -----------------------------------------------------------------------------
# Base Models
# -----------------------------------------------------------------------------
class PlatformSelectedPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    platform: Literal['NETFLIX', 'MAX', 'PRIME_VIDEO', 'DISNEY_PLUS', 'YOUTUBE', 'SPOTIFY']

class TextCommandPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str

# -----------------------------------------------------------------------------
# Client Messages
# -----------------------------------------------------------------------------
class PlatformSelectedMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['PLATFORM_SELECTED']
    requestId: str
    payload: PlatformSelectedPayload

class TextCommandMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['TEXT_COMMAND']
    requestId: str
    payload: TextCommandPayload

ClientMessage = Annotated[
    AuthMessage | PairDeviceMessage |
    VolumeGetMessage | VolumeSetMessage | VolumeStepMessage | VolumeToggleMuteMessage |
    PlatformSelectedMessage | TextCommandMessage,
    Field(discriminator='type')
]

# -----------------------------------------------------------------------------
# Server Messages
# -----------------------------------------------------------------------------
class StateUpdateMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['STATE_UPDATE'] = 'STATE_UPDATE'
    state: str

class CommandResultMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['COMMAND_RESULT'] = 'COMMAND_RESULT'
    requestId: str
    success: bool
    message: str
    data: Optional[Any] = None

class ErrorMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['ERROR'] = 'ERROR'
    requestId: str
    code: str
    message: str
