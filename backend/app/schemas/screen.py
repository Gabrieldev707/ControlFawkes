"""Tocar na foto da tela, e escolher um perfil já cadastrado.

As duas mensagens acabam no mesmo lugar — um clique dentro da janela da
plataforma —, mas chegam por caminhos diferentes: uma traz a posição do dedo,
a outra traz o identificador de um perfil cuja posição já está guardada.

A posição viaja como fração de 0 a 1, nunca como pixel. É o que faz o cadastro
sobreviver a mover a janela para o outro monitor, que é exatamente o que
aconteceu enquanto isto era medido.
"""

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.platform import Platform


ScreenAction: TypeAlias = Literal["SCREEN_TAP", "PROFILE_SELECT"]

SCREEN_ACTIONS: tuple[ScreenAction, ...] = ("SCREEN_TAP", "PROFILE_SELECT")

class ScreenTapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform
    # Fora de 0..1 não é dedo em imagem, é mensagem malformada. O clique ainda
    # é preso dentro da janela mais adiante, mas recusar aqui evita tratar como
    # legítimo o que não é.
    x: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    y: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    # Duplo clique existe para o caso de um item que só abre assim; o padrão é
    # simples porque é o que a tela de perfil e a de login esperam.
    double: bool = False


class ScreenTapMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["SCREEN_TAP"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: ScreenTapPayload


class ProfileSelectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform
    profileId: str = Field(min_length=1, max_length=64)


class ProfileSelectMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: Literal["PROFILE_SELECT"]
    requestId: str = Field(min_length=1, max_length=128)
    payload: ProfileSelectPayload


class ScreenCommandData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["SCREEN_CONTROL"] = "SCREEN_CONTROL"
    action: ScreenAction
    platform: Platform
    executed: bool
