from typing import Any, Literal, Optional, Annotated
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Base Models
# -----------------------------------------------------------------------------
class AuthPayload(BaseModel):
    token: str

class PlatformSelectedPayload(BaseModel):
    platform: Literal['NETFLIX', 'MAX', 'PRIME_VIDEO', 'DISNEY_PLUS', 'YOUTUBE', 'SPOTIFY']

class TextCommandPayload(BaseModel):
    query: str

# -----------------------------------------------------------------------------
# Client Messages
# -----------------------------------------------------------------------------
class AuthMessage(BaseModel):
    type: Literal['AUTH']
    requestId: str
    payload: AuthPayload

class PlatformSelectedMessage(BaseModel):
    type: Literal['PLATFORM_SELECTED']
    requestId: str
    payload: PlatformSelectedPayload

class TextCommandMessage(BaseModel):
    type: Literal['TEXT_COMMAND']
    requestId: str
    payload: TextCommandPayload

ClientMessage = Annotated[
    AuthMessage | PlatformSelectedMessage | TextCommandMessage,
    Field(discriminator='type')
]

# -----------------------------------------------------------------------------
# Server Messages
# -----------------------------------------------------------------------------
class StateUpdateMessage(BaseModel):
    type: Literal['STATE_UPDATE'] = 'STATE_UPDATE'
    state: str

class CommandResultMessage(BaseModel):
    type: Literal['COMMAND_RESULT'] = 'COMMAND_RESULT'
    requestId: str
    success: bool
    message: str
    data: Optional[Any] = None

class ErrorMessage(BaseModel):
    type: Literal['ERROR'] = 'ERROR'
    requestId: str
    code: str
    message: str
