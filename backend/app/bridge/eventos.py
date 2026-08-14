"""Validação do que chega pela ponte.

O Master Loop escreveu a regra e ela vale literalmente: **a extensão não é
tratada como fonte confiável só porque é nossa.** Ela roda dentro do navegador,
lê um DOM que nenhum de nós controla, e um serviço pode mudar o player amanhã
sem avisar. O que ela manda é entrada, e entrada se valida.

O que este módulo NÃO faz, de propósito: não decide autoridade de campo (isso é
o Merger, Fase 7), não olha frescor (Fase 8), não decide se conta como assistido
(Fase 9). Aqui a pergunta é só uma — **isto é uma mensagem utilizável?**

## Sobre "valores impossíveis"

A parte que rende. Um `currentTime` negativo é fácil; o que morde é o
plausível-mas-errado, que foi exatamente o defeito do Batman e o da linha do
tempo congelada do Chrome. Então:

    currentTime > duration     recusado. Não existe estar além do fim, e um
                               valor assim é sinal de leitura misturada entre
                               duas reproduções.
    duration <= 0              vira ausente. Zero não é duração; é ao vivo ou
                               metadata que não chegou.
    playbackRate fora de faixa  o HTML permite 0.0625 a 16; fora disso é lixo.
    timestamp no futuro        o relógio da aba pode estar errado, mas não
                               adiantado dez minutos.

Nada aqui "conserta" valor: ou ele passa, ou o campo vira ausente, ou a
mensagem é recusada inteira. Corrigir silenciosamente é como o número errado
entra no sistema parecendo certo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import math


PROTOCOL_VERSION = 1

# A lista curta da Fase 6. Nada de inventar evento antes de haver consumidor —
# cada tipo aqui tem quem o receba do outro lado.
TIPOS: frozenset[str] = frozenset({
    "SESSION_STARTED",
    "MEDIA_CHANGED",
    "PLAY",
    "PAUSE",
    "SEEK",
    "ENDED",
    "POSITION_SYNC",
    "SESSION_ENDED",
})

ESTADOS: frozenset[str] = frozenset({"playing", "paused", "ended", "unknown"})

# O HTML permite de 0.0625 a 16. Fora disso não é velocidade, é lixo.
RATE_MINIMO = 0.0625
RATE_MAXIMO = 16.0

# Tolerância do relógio da aba contra o do servidor. Generosa de propósito: a
# máquina pode estar com o horário torto, e recusar por isso calaria a ponte
# inteira por um motivo que não tem nada a ver com mídia.
DERIVA_MAXIMA_SEGUNDOS = 600.0

# `currentTime` pode passar de `duration` por arredondamento no fim do vídeo.
# Meio segundo cobre isso sem deixar passar leitura de outra reprodução.
FOLGA_NO_FIM = 0.5


@dataclass(frozen=True)
class Recusa:
    code: str
    detail: str


@dataclass(frozen=True)
class EventoDeMidia:
    """Uma mensagem da ponte que passou pela validação.

    Os campos temporais são `None` quando ausentes ou inutilizáveis — e os dois
    casos dão no mesmo para quem consome: não dá para afirmar.
    """

    messageType: str
    sessionId: str
    tabId: int | None
    windowId: int | None
    provider: str | None
    playbackState: str | None
    currentTime: float | None
    duration: float | None
    playbackRate: float | None
    audible: bool | None
    muted: bool | None
    timestamp: float


def _numero(valor: object) -> float | None:
    """Um número real e finito, ou nada.

    `bool` é subclasse de `int` em Python, e `True` viraria `1.0` sem esta
    checagem — um `currentTime` de um segundo que ninguém mediu.
    """
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = float(valor)
    if math.isnan(numero) or math.isinf(numero):
        return None
    return numero


def validar(mensagem: object, agora: float) -> EventoDeMidia | Recusa:
    """A mensagem crua vira evento, ou vira recusa com motivo."""
    if not isinstance(mensagem, dict):
        return Recusa("INVALID_MESSAGE", "A mensagem precisa ser um objeto.")

    if mensagem.get("protocolVersion") != PROTOCOL_VERSION:
        return Recusa(
            "PROTOCOL_VERSION_MISMATCH",
            f"Esperava {PROTOCOL_VERSION}, veio {mensagem.get('protocolVersion')!r}.",
        )

    tipo = mensagem.get("messageType")
    if tipo not in TIPOS:
        return Recusa("UNKNOWN_MESSAGE_TYPE", f"Tipo desconhecido: {tipo!r}.")

    marca = _numero(mensagem.get("timestamp"))
    if marca is None:
        return Recusa("INVALID_TIMESTAMP", "Sem marca de tempo utilizável.")
    # Milissegundos do lado do navegador, segundos do lado do servidor.
    marca_em_segundos = marca / 1000.0
    if marca_em_segundos - agora > DERIVA_MAXIMA_SEGUNDOS:
        return Recusa(
            "INVALID_TIMESTAMP",
            f"Marca {marca_em_segundos - agora:.0f}s no futuro.",
        )

    payload = mensagem.get("payload")
    if not isinstance(payload, dict):
        return Recusa("INVALID_PAYLOAD", "Payload ausente ou não é objeto.")

    sessao = payload.get("sessionId")
    if not isinstance(sessao, str) or not sessao.strip() or len(sessao) > 128:
        return Recusa("INVALID_SESSION_ID", "sessionId ausente ou fora do formato.")

    aba = payload.get("tabId")
    if aba is not None and (isinstance(aba, bool) or not isinstance(aba, int)):
        return Recusa("INVALID_TAB_ID", f"tabId inesperado: {aba!r}.")
    janela = payload.get("windowId")
    if janela is not None and (isinstance(janela, bool) or not isinstance(janela, int)):
        return Recusa("INVALID_WINDOW_ID", f"windowId inesperado: {janela!r}.")

    provedor = payload.get("provider")
    if provedor is not None and (not isinstance(provedor, str) or len(provedor) > 253):
        return Recusa("INVALID_PROVIDER", "provider fora do formato.")

    estado = payload.get("playbackState")
    if estado is not None and estado not in ESTADOS:
        return Recusa("INVALID_PLAYBACK_STATE", f"Estado desconhecido: {estado!r}.")

    # Duração zero ou negativa não é duração: é ao vivo, ou metadata que ainda
    # não chegou. Vira ausente em vez de recusar a mensagem — o resto dela
    # continua valendo.
    duracao = _numero(payload.get("duration"))
    if duracao is not None and duracao <= 0:
        duracao = None

    posicao = _numero(payload.get("currentTime"))
    if posicao is not None and posicao < 0:
        posicao = None
    # Estar ALÉM do fim não é um valor ruim, é um valor de outra reprodução.
    # Foi assim que a linha do tempo congelada do Chrome enganou o cartão: a
    # posição cabia na duração e parecia plausível. Aqui não cabe.
    if posicao is not None and duracao is not None and posicao > duracao + FOLGA_NO_FIM:
        return Recusa(
            "IMPOSSIBLE_POSITION",
            f"currentTime {posicao} além de duration {duracao}.",
        )

    ritmo = _numero(payload.get("playbackRate"))
    if ritmo is not None and not (RATE_MINIMO <= ritmo <= RATE_MAXIMO):
        ritmo = None

    def booleano(nome: str) -> bool | None:
        valor = payload.get(nome)
        return valor if isinstance(valor, bool) else None

    return EventoDeMidia(
        messageType=tipo,
        sessionId=sessao,
        tabId=aba,
        windowId=janela,
        provider=provedor,
        playbackState=estado,
        currentTime=posicao,
        duration=duracao,
        playbackRate=ritmo,
        audible=booleano("audible"),
        muted=booleano("muted"),
        timestamp=marca_em_segundos,
    )
