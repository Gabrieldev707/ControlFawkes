"""Os contratos da camada de mídia — procedência por campo, sem número mágico.

Este módulo não faz nada. Ele define o vocabulário que o Media Merger (Fase 7)
vai usar, e a Fase 2 existe para que esse vocabulário seja decidido ANTES de
haver código dependendo dele.

Duas decisões estão congeladas aqui, e as duas são invariantes do Master Loop.

## 1. Procedência por campo, e não `confidence` numérico

A tentação é marcar cada dado com um `confidence: 0.98` e deixar o maior
vencer. Isso parece rigor e é o contrário: o número não sai de lugar nenhum,
ninguém sabe dizer por que 0.98 vence 0.95, e a decisão do Merger vira
emergente — o pior tipo, porque não se testa.

O que substitui: `MediaField`, com a FONTE explícita e um booleano. A pergunta
deixa de ser "qual fonte tem mais confiança?" e passa a ser "esta fonte é
autoridade para ESTE campo, e ela ainda está saudável?".

Isto não é invenção. O `NowPlaying.trustworthy` que já existe em produção é
exatamente este booleano, e `PLATAFORMAS_COM_OBRA_NA_JANELA` é exatamente a
tabela de capacidade por serviço. A Fase 2 generaliza o que já funciona.

## 2. Três perguntas diferentes, e não uma

O bug do Batman nasceu de fundir três perguntas numa só:

    playbackState   o player está tecnicamente reproduzindo?
    audible         saiu som recentemente?
    consumptionState  há evidência suficiente para contar como assistido?

`video.paused === false` responde a PRIMEIRA. Uma aba muda, uma aba em segundo
plano, uma janela esquecida: todas têm `paused === false`. Contar tempo com base
nisso foi o que somou 129 minutos de um filme que ninguém estava vendo.

`consumptionState` é DERIVADO — nenhuma fonte o reporta, porque nenhuma fonte
sozinha sabe. Ver `app/bridge/consumo.py` na Fase 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ── Fontes ────────────────────────────────────────────────────────────────

#   smtc                 API de mídia do Windows. Sabe estado e linha do tempo.
#   window-title         O título da janela. Sabe o nome, com ressalvas por
#                        serviço — ver PLATAFORMAS_COM_OBRA_NA_JANELA.
#   html-media-element   O <video> da página, via extensão. Autoridade sobre
#                        tempo e estado técnico.
#   provider-adapter     Adapter específico do serviço. Sabe o que só ele sabe:
#                        obra, episódio, temporada.
Fonte = Literal[
    "smtc",
    "window-title",
    "html-media-element",
    "provider-adapter",
]


@dataclass(frozen=True)
class MediaField[T]:
    """Um valor, de onde ele veio, e se dá para afirmar.

    `trustworthy` não é "o dado parece bom". É "esta fonte tem autoridade para
    este campo, neste serviço". O Max publica um título na janela e ele É um
    título — só que do episódio, não da obra. O valor está certo; a afirmação
    "isto é a obra" é que seria falsa.
    """

    value: T | None
    source: Fonte | None
    trustworthy: bool

    @classmethod
    def ausente(cls) -> MediaField[T]:
        """Ninguém respondeu. Diferente de "respondeu que não sabe"."""
        return cls(value=None, source=None, trustworthy=False)

    @property
    def utilizavel(self) -> bool:
        """Dá para usar este campo para afirmar alguma coisa?

        Valor presente E fonte com autoridade. Um dos dois sozinho não basta —
        e foi justamente "tem valor, logo serve" que pôs o nome de um episódio
        no lugar do nome da obra no histórico.
        """
        return self.value is not None and self.trustworthy


# ── Estados ───────────────────────────────────────────────────────────────

# O estado TÉCNICO do player. Responde "o elemento está reproduzindo?" e nada
# além disso. Não confundir com consumo.
EstadoDeReproducao = Literal["playing", "paused", "ended", "unknown"]

# O tipo do que está tocando, quando dá para saber.
TipoDeMidia = Literal["movie", "episode", "video", "unknown"]


@dataclass(frozen=True)
class SessaoCanonica:
    """O resultado do Media Merger: uma sessão, campo a campo, com procedência.

    Cada campo carrega a própria origem. Isso é o que permite responder, em
    log e em teste, "de onde veio este título?" — pergunta que hoje não tem
    resposta, porque a composição acontece dentro de uma função só.

    Nenhuma fonte "vence" esta estrutura inteira. Se um dia algum campo passar
    a ser preenchido em bloco por uma fonte, o critério de implementação
    incorreta nº 5 do Master Loop foi violado.
    """

    provider: MediaField[str]
    mediaType: MediaField[TipoDeMidia]

    workTitle: MediaField[str]
    episodeTitle: MediaField[str]
    seasonNumber: MediaField[int]
    episodeNumber: MediaField[int]

    playbackState: MediaField[EstadoDeReproducao]
    # Separado de `playbackState` de propósito. Ver a docstring do módulo.
    audible: MediaField[bool]
    muted: MediaField[bool]

    currentTime: MediaField[float]
    duration: MediaField[float]
    playbackRate: MediaField[float]

    @classmethod
    def vazia(cls) -> SessaoCanonica:
        """Uma sessão em que ninguém respondeu nada.

        Existe para o Merger poder partir daqui e ir preenchendo campo a campo,
        em vez de montar um dicionário e torcer para não faltar chave.
        """
        return cls(**{nome: MediaField.ausente() for nome in cls.__annotations__})

    def procedencia(self) -> dict[str, Fonte | None]:
        """De onde veio cada campo. Para log, teste e diagnóstico.

        É o que transforma "o título está errado" em "o título veio da janela,
        e para a Netflix a janela não é autoridade para título".
        """
        return {
            nome: getattr(self, nome).source
            for nome in self.__annotations__
        }
