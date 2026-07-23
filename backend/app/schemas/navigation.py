"""Navegação direcional para interfaces de TV.

Contrato separado do teclado remoto de propósito: o direcional precisa de
auto-repeat ao segurar a seta, e o teclado não. Compartilhar um tipo faria os
dois dividirem o mesmo limite de taxa, prejudicando os dois usos. O backend
reaproveita internamente o adapter de teclas seguras.

NAVIGATE_HOME fica de fora até existir um comportamento seguro e definido: não
há tecla única de "home" que valha para todas as interfaces.
"""

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from app.input.keyboard import SafeKey


NavigationAction: TypeAlias = Literal[
    "NAVIGATE_UP",
    "NAVIGATE_DOWN",
    "NAVIGATE_LEFT",
    "NAVIGATE_RIGHT",
    "NAVIGATE_CONFIRM",
    "NAVIGATE_BACK",
]

NAVIGATION_ACTIONS: tuple[NavigationAction, ...] = (
    "NAVIGATE_UP",
    "NAVIGATE_DOWN",
    "NAVIGATE_LEFT",
    "NAVIGATE_RIGHT",
    "NAVIGATE_CONFIRM",
    "NAVIGATE_BACK",
)

# Mapeamento fechado para as teclas já allowlisted do teclado remoto.
NAVIGATION_KEYS: dict[NavigationAction, SafeKey] = {
    "NAVIGATE_UP": "ARROW_UP",
    "NAVIGATE_DOWN": "ARROW_DOWN",
    "NAVIGATE_LEFT": "ARROW_LEFT",
    "NAVIGATE_RIGHT": "ARROW_RIGHT",
    "NAVIGATE_CONFIRM": "ENTER",
    "NAVIGATE_BACK": "ESCAPE",
}

NAVIGATION_LABELS: dict[NavigationAction, str] = {
    "NAVIGATE_UP": "Cima",
    "NAVIGATE_DOWN": "Baixo",
    "NAVIGATE_LEFT": "Esquerda",
    "NAVIGATE_RIGHT": "Direita",
    "NAVIGATE_CONFIRM": "OK",
    "NAVIGATE_BACK": "Voltar",
}

# Só as setas repetem ao segurar. Confirmar e voltar repetindo seriam
# destrutivos: entrariam em vários itens ou sairiam de várias telas.
REPEATABLE_ACTIONS: frozenset[NavigationAction] = frozenset({
    "NAVIGATE_UP",
    "NAVIGATE_DOWN",
    "NAVIGATE_LEFT",
    "NAVIGATE_RIGHT",
})


class NavigationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocolVersion: Literal[1]
    type: NavigationAction
    requestId: str = Field(min_length=1, max_length=128)
