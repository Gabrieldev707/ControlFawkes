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

# Teto de texto vindo do adapter. Um nome de obra não tem 500 caracteres; um
# `textContent` de DOM hostil tem. Corta em vez de recusar: o resto da mensagem
# continua valendo, e um nome truncado ainda é melhor do que nenhum.
LIMITE_DE_TEXTO = 300

# Temporada e episódio não passam disto. Acima é ano, ou pedaço do nome que
# virou número por acidente.
LIMITE_DE_CONTAGEM = 999


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
    # Fase 10: o que só a página sabe. `None` quando o serviço não tem adapter
    # — que é o caso de cinco dos seis, e não é falta: eles nomeiam a obra na
    # janela. Ver `providers/netflix.js`.
    workTitle: str | None = None
    episodeTitle: str | None = None
    seasonNumber: int | None = None
    episodeNumber: int | None = None
    #: Onde o vídeo está NA JANELA, em fração de 0 a 1.
    #:
    #: Existe para a tela cheia acertar o vídeo. Ela é um duplo clique, e o
    #: clique mirava o centro da JANELA — o que só acerta enquanto o vídeo
    #: ocupa o meio da tela. Medido no Prime em 26/08/2026: o vídeo toca em
    #: `/detail/`, com a lista de episódios e a sinopse em volta.
    #:
    #: Fração e não pixel: sobrevive ao escalonamento do Windows, e é a mesma
    #: forma que o toque na tela espelhada já usa.
    videoCentroX: float | None = None
    videoCentroY: float | None = None
    #: A ordem em que a ABA emitiu esta mensagem. Fase 17.
    #:
    #: O content script já numerava (`seq: sequencia++` em `index.js`) e o
    #: backend ignorava por completo — o campo existia e não era lido. Sem ele,
    #: uma mensagem que chegasse fora de ordem rebobinava a posição em
    #: silêncio: um `POSITION_SYNC` antigo sobrescrevendo um recente faz a
    #: barra andar para trás sem nada ter acontecido na tela.
    #:
    #: Por SESSÃO, e não global: cada aba tem o seu contador, e comparar entre
    #: abas não significa nada.
    seq: int | None = None
    #: Identidade de reprodução da própria página ("/watch/81234567").
    pageId: str | None = None
    # Fase 10 — o tempo que o `<video>` da página NÃO sabe.
    #
    # Existe porque num serviço o elemento de mídia pode ser cego para o
    # próprio conteúdo. Medido no Disney+, no mesmo instante:
    #
    #     slider do player   146s de 3043s   ("2:26 of 50:43")
    #     video.currentTime  50.8
    #     video.duration     Infinity
    #     video.seekable     [0, 62]
    #
    # O `seekable` inteiro cabia em 62 segundos, num episódio de cinquenta
    # minutos: o `<video>` só conhece a janela DASH que está montando. A
    # posição do Disney+ nunca esteve certa — não por regressão, mas porque a
    # única fonte que existia era a errada.
    #
    # Campos SEPARADOS de `currentTime`/`duration`, e não substituindo-os: são
    # outra fonte, com outra autoridade, e quem escolhe entre elas é o Merger.
    # Sobrescrever aqui seria decidir autoridade dentro da validação.
    adapterPosition: float | None = None
    adapterDuration: float | None = None
    #: O título da ABA, cru. Vale para TODO serviço, com ou sem adapter — a
    #: janela do Chrome só publica o título da aba ativa, e a extensão vê o da
    #: aba dela sempre.
    documentTitle: str | None = None
    # Fase 14 — telemetria de aba. `active`, `windowFocused` e `tabMuted` vêm do
    # `sender` no service worker, que é o Chrome falando; `pictureInPicture`,
    # `visible` e os dois intervalos vêm da própria página.
    active: bool | None = None
    windowFocused: bool | None = None
    tabMuted: bool | None = None
    pictureInPicture: bool | None = None
    visible: bool | None = None
    #: Milissegundos desde o último `play` e desde qualquer evento de mídia.
    #: Intervalo e não carimbo: o relógio da aba pode estar torto, e um
    #: intervalo continua utilizável mesmo assim.
    msDesdeUltimoPlay: float | None = None
    msDesdeUltimoEvento: float | None = None


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

    # O tempo do adapter, pelas MESMAS regras do tempo do elemento — e apurado
    # em separado, porque as duas fontes podem discordar sem que nenhuma esteja
    # com defeito. No Disney+ elas discordam sempre: 146 contra 50.8, no mesmo
    # instante, e a certa é a do adapter.
    duracao_do_adapter = _numero(payload.get("adapterDuration"))
    if duracao_do_adapter is not None and duracao_do_adapter <= 0:
        duracao_do_adapter = None

    posicao_do_adapter = _numero(payload.get("adapterPosition"))
    if posicao_do_adapter is not None and posicao_do_adapter < 0:
        posicao_do_adapter = None
    if (
        posicao_do_adapter is not None
        and duracao_do_adapter is not None
        and posicao_do_adapter > duracao_do_adapter + FOLGA_NO_FIM
    ):
        # Aqui o par vira ausente em vez de recusar a mensagem inteira: o
        # `currentTime` do elemento e a metadata continuam utilizáveis, e
        # descartá-los junto deixaria o serviço sem cartão nenhum por causa de
        # uma leitura de DOM ruim.
        posicao_do_adapter = None
        duracao_do_adapter = None

    ritmo = _numero(payload.get("playbackRate"))
    if ritmo is not None and not (RATE_MINIMO <= ritmo <= RATE_MAXIMO):
        ritmo = None

    def booleano(nome: str) -> bool | None:
        valor = payload.get(nome)
        return valor if isinstance(valor, bool) else None

    # A metadata do adapter é entrada como qualquer outra, e é validada como
    # qualquer outra. Ela vem do DOM de um serviço que ninguém aqui controla:
    # ser nossa a extensão não a torna confiável.
    def texto(nome: str) -> str | None:
        valor = payload.get(nome)
        if not isinstance(valor, str):
            return None
        limpo = valor.strip()
        # Vazio é ausente, e não uma obra chamada "". O teto existe porque um
        # DOM hostil pode devolver um documento inteiro como `textContent`.
        return limpo[:LIMITE_DE_TEXTO] if limpo else None

    def intervalo(nome: str) -> float | None:
        """Milissegundos desde alguma coisa. Negativo é relógio torto."""
        valor = _numero(payload.get(nome))
        return valor if valor is not None and valor >= 0 else None

    def fracao(nome: str) -> float | None:
        """Uma posição relativa dentro da janela: de 0 a 1, e nada fora disso.

        Fora da faixa não é "quase certo": é outra janela, ou uma leitura de um
        vídeo rolado para fora da tela. Clicar ali erraria o alvo com a mesma
        confiança de acertar.
        """
        valor = _numero(payload.get(nome))
        return valor if valor is not None and 0.0 <= valor <= 1.0 else None

    def contagem_livre(nome: str) -> int | None:
        """Um inteiro não-negativo, sem o teto de `contagem`.

        A sequência da aba não é temporada nem episódio: ela cresce sem limite
        enquanto a aba viver, e cortá-la em 999 faria toda mensagem depois da
        milésima parecer ausente.
        """
        valor = payload.get(nome)
        if isinstance(valor, bool) or not isinstance(valor, int):
            return None
        return valor if valor >= 0 else None

    def contagem(nome: str) -> int | None:
        valor = payload.get(nome)
        if isinstance(valor, bool) or not isinstance(valor, int):
            return None
        # Zero não existe em nenhuma das duas contagens; número alto demais é
        # ano ou pedaço do nome que virou número por acidente.
        return valor if 1 <= valor <= LIMITE_DE_CONTAGEM else None

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
        workTitle=texto("workTitle"),
        episodeTitle=texto("episodeTitle"),
        seasonNumber=contagem("seasonNumber"),
        episodeNumber=contagem("episodeNumber"),
        pageId=texto("pageId"),
        videoCentroX=fracao("videoCentroX"),
        videoCentroY=fracao("videoCentroY"),
        seq=contagem_livre("seq"),
        adapterPosition=posicao_do_adapter,
        adapterDuration=duracao_do_adapter,
        documentTitle=texto("documentTitle"),
        active=booleano("active"),
        windowFocused=booleano("windowFocused"),
        tabMuted=booleano("tabMuted"),
        pictureInPicture=booleano("pictureInPicture"),
        visible=booleano("visible"),
        msDesdeUltimoPlay=intervalo("msDesdeUltimoPlay"),
        msDesdeUltimoEvento=intervalo("msDesdeUltimoEvento"),
    )
