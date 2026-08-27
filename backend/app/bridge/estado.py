"""O que a ponte disse, e se isso ainda vale AGORA.

A Fase 6 fez os eventos chegarem. A rota os validava, respondia `ok` e os
jogava fora — o comentário dela dizia, com todas as letras, que o Merger
entraria "na Fase 8, quando houver frescor para alimentá-lo". Este módulo é
esse frescor.

Medido no `host.log` desta máquina, em 25/08/2026:

    00:19:52  POSITION_SYNC  playing  currentTime=2974.46  duration=3238
    00:19:59  SEEK           paused   currentTime=0        duration=2921.006
    00:20:00  PLAY           playing  currentTime=0.003    duration=2921.006

O dado certo já estava chegando. Na mesma sessão, o histórico gravou
`posicao 391.03 / 3238.0` — a duração bate, a posição está dois mil e
quinhentos segundos atrás. O número bom entrava pelo cano e era descartado na
saída.

## Por que "frescor" não é a mesma pergunta que "capacidade"

É a distinção que o gate da Fase 8 exige, e confundi-las é o erro que ela
existe para travar.

    capacidade   esta fonte SABE responder este campo, neste serviço? A janela
                 do Max sempre publica título e ele sempre é o do episódio.
                 Esperar mais não melhora. Mora em
                 `PLATAFORMAS_COM_OBRA_NA_JANELA`.

    frescor      o que esta fonte disse ainda descreve o AGORA? Um
                 `currentTime` de trinta segundos atrás estava certo quando foi
                 lido e não está mais. Mora aqui.

Uma janela lida neste milissegundo continua não sendo autoridade para o nome da
obra na Netflix. Frescor não promove ninguém.

## O que este módulo NÃO faz

Não decide qual aba vence quando há várias tocando — isso é a Fase 15, e o
desempate daqui é o mínimo para não quebrar com duas abas abertas, não um
árbitro. Não LÊ nome de obra — quem lê é o adapter dentro da página
(`providers/netflix.js`, Fase 10); aqui ele só é guardado e declarado. E não
conta tempo assistido: isso é a política da Fase 9, em `consumo.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import time

from app.bridge.contratos import MediaField
from app.bridge.eventos import EventoDeMidia
from app.bridge.arbitro import escolher
from app.bridge.merger import Leitura
from app.schemas.ws import Platform


# O batimento da extensão é de 10 em 10 segundos — `SEGUNDOS_ENTRE_BATIMENTOS`
# em `content/index.js`. Mas o que CHEGA não é de dez em dez.
#
# Medido no `host.log` desta máquina, em 25/08/2026, com o vídeo tocando numa
# aba de segundo plano:
#
#     15:36:56  POSITION_SYNC  currentTime=1463.2
#     15:37:56  POSITION_SYNC  currentTime=1522.5
#     15:38:56  POSITION_SYNC  currentTime=1581.7
#
# Sessenta segundos exatos entre batimentos, e não dez. O Chrome estrangula
# `setInterval` em aba que não está visível — é comportamento documentado do
# navegador, não defeito da extensão, e não há como desligá-lo de dentro da
# página. A aba de segundo plano é justamente o caso normal de quem assiste em
# tela cheia noutro monitor ou deixa o vídeo tocando enquanto usa outra coisa.
#
# Os prazos abaixo foram escritos para o batimento de 10s e, com o de 60s,
# faziam o oposto do que prometiam: o tempo envelhecia ENTRE batimentos e a
# sessão era despejada exatamente quando o próximo chegava. A ponte piscava
# entre "tem sessão" e "não tem", e cada piscada derrubava a fusão.
#
# Refeitos sobre o batimento REAL (60s), mantendo a mesma folga de antes.

#: Depois disto, o que a ponte disse sobre TEMPO não descreve mais o agora.
#: Dois batimentos e meio do batimento estrangulado.
#:
#: Ser generoso aqui custa pouco: com `playing`, a posição é extrapolada a
#: partir do último valor medido, e extrapolar reprodução contínua por um
#: minuto erra em fração de segundo. O que este prazo protege é contra
#: extrapolar uma reprodução que PAROU sem avisar — e para isso dois minutos e
#: meio ainda é curto o bastante.
SEGUNDOS_ATE_O_TEMPO_ENVELHECER = 150.0

#: Depois disto, a ponte é considerada desconectada. Bem mais folgado que o
#: prazo do tempo, porque as duas perguntas são diferentes: uma aba pode estar
#: viva e sem publicar posição nova, e chamar isso de "desconectada" apagaria a
#: informação de que a extensão está lá.
#:
#: Cinco minutos: sobrevive a vários batimentos estrangulados perdidos. Uma aba
#: que fecha de verdade manda `SESSION_ENDED` e some na hora, sem esperar isto.
SEGUNDOS_ATE_DESCONECTAR = 300.0


# O `provider` que a extensão manda é `location.hostname`, e o resto do sistema
# fala em `Platform`. A tradução precisa existir para uma coisa só, e é a mais
# importante deste módulo: NÃO aplicar o tempo de uma aba da Netflix a uma
# sessão do Prime Video.
#
# Por sufixo e não por igualdade: o mesmo serviço atende em vários domínios
# ("www.netflix.com", "netflix.com") e em domínios regionais.
_HOSTS: tuple[tuple[str, Platform], ...] = (
    ("netflix.com", "NETFLIX"),
    ("youtube.com", "YOUTUBE"),
    ("youtu.be", "YOUTUBE"),
    ("hbomax.com", "MAX"),
    ("max.com", "MAX"),
    ("disneyplus.com", "DISNEY_PLUS"),
    ("primevideo.com", "PRIME_VIDEO"),
    ("amazon.com", "PRIME_VIDEO"),
    ("amazon.com.br", "PRIME_VIDEO"),
    ("open.spotify.com", "SPOTIFY"),
    ("spotify.com", "SPOTIFY"),
)


def plataforma_do_host(provider: str | None) -> Platform | None:
    """O serviço por trás do hostname que a aba declarou.

    `None` quando não é um serviço conhecido — e aí o tempo daquela aba não é
    aplicado a nada. Um vídeo qualquer numa página qualquer não pode carimbar a
    linha do tempo do que está tocando na Netflix.
    """
    if not provider:
        return None
    host = provider.strip().lower().rstrip(".")
    if not host:
        return None
    for sufixo, plataforma in _HOSTS:
        if host == sufixo or host.endswith(f".{sufixo}"):
            return plataforma
    return None


@dataclass(frozen=True)
class SaudeDaPonte:
    """A saúde da ponte, na forma que a ponte de fato falha.

    Repare que não é a mesma forma da SMTC nem a do Window Title, e isso é
    deliberado — ver a docstring de `saude.py`. A ponte falha por SILÊNCIO: a
    aba fecha, o navegador sai, a extensão é desligada. O que se mede é quando
    ela falou pela última vez.

    E `lastSeen` é separado de `lastPositionUpdate` porque as duas respostas
    divergem no caso que importa: uma aba pausada continua mandando batimento
    (viva) sem mexer a posição (tempo velho).
    """

    #: A ponte falou dentro do prazo?
    connected: bool
    #: Segundos desde o último evento de qualquer tipo. `None` = nunca falou.
    lastSeen: float | None
    #: Segundos desde o último evento que trouxe posição. `None` = nenhum.
    lastPositionUpdate: float | None


@dataclass(frozen=True)
class SessaoDaPonte:
    """Uma reprodução que a extensão está observando."""

    sessionId: str
    #: Qual aba e qual janela do Chrome. Vêm do `sender` no service worker — a
    #: página não tem voz sobre qual aba ela é.
    tabId: int | None
    windowId: int | None
    platform: Platform | None
    playbackState: str | None
    currentTime: float | None
    duration: float | None
    playbackRate: float | None
    muted: bool | None
    audible: bool | None
    #: Fase 10 — o que só a página sabe. `None` para serviço sem adapter.
    workTitle: str | None
    episodeTitle: str | None
    seasonNumber: int | None
    episodeNumber: int | None
    pageId: str | None
    #: Fase 10 — o tempo lido da PÁGINA, quando o `<video>` é cego para ele.
    #: No Disney+ o elemento reporta a janela DASH que está montando, e não o
    #: episódio: medido, `currentTime=50.8` e `duration=Infinity` enquanto o
    #: player mostrava 146s de 3043s. Ver `adapterPosition` em `eventos.py`.
    adapterPosition: float | None
    adapterDuration: float | None
    #: O título da aba, cru. Ver `documentTitle` em `eventos.py`.
    documentTitle: str | None
    #: Fase 14 — telemetria de aba, para a política da Fase 15 sair de dados.
    active: bool | None
    windowFocused: bool | None
    tabMuted: bool | None
    pictureInPicture: bool | None
    visible: bool | None
    msDesdeUltimoPlay: float | None
    msDesdeUltimoEvento: float | None
    #: Relógio monotônico do último evento desta sessão.
    visto_em: float
    #: Relógio monotônico de quando `currentTime` chegou. `None` = nunca.
    posicao_em: float | None
    #: A duração já aumentou nesta sessão? Ver `duracao_confiavel`.
    duracao_cresceu: bool = False
    #: A maior sequência já vista desta sessão. Ver `registrar`.
    ultimo_seq: int | None = None
    #: Onde o vídeo está na janela, em fração. Ver `videoCentroX` em
    #: `eventos.py` — existe para a tela cheia acertar o vídeo.
    videoCentroX: float | None = None
    videoCentroY: float | None = None
    #: Onde está o botão de tela cheia. Ver `telaCheiaX` em `eventos.py`.
    telaCheiaX: float | None = None
    telaCheiaY: float | None = None

    @property
    def tocando(self) -> bool:
        return self.playbackState == "playing"

    @property
    def duracao_confiavel(self) -> bool:
        """A duração descreve a OBRA, ou só o que já foi baixado?

        ## O que se mediu

        Disney+, com Demolidor: Renascido tocando, três leituras seguidas:

            pos=236.5  duration=252
            pos=306.5  duration=316
            pos=360.6  duration=372

        A duração CRESCE, sempre uns segundos à frente da posição. Isso não é
        um vídeo de cinco minutos: é MSE. O player monta o vídeo por segmentos,
        e `video.duration` reporta a borda do BUFFER enquanto o resto não
        chegou.

        A consequência na tela é grosseira e constante: a barra fica sempre
        quase cheia, o "faltam X" fica sempre em segundos, e um episódio de
        cinquenta minutos se anuncia como se estivesse acabando. Foi isto que o
        usuário chamou de "contagem falsa" — e ele estava certo.

        ## Por que crescer é a prova, e o tamanho não é

        A primeira tentativa de conserto cortou por duração pequena — "menos de
        90 segundos é prévia". Estava errada por dois lados: suprimia
        reprodução de verdade no primeiro minuto (quando o buffer ainda é
        curto) e não pegava o caso medido, que já passava de 250 segundos.

        Uma duração que AUMENTA não pode ser a duração de nada. Uma que fica
        parada pode ser — e é o que a Netflix publica desde o começo, que é por
        que só ela estava certa.
        """
        return self.duration is not None and not self.duracao_cresceu

    def posicao_agora(self, agora: float) -> float | None:
        """Onde a reprodução está NESTE instante.

        A extensão bate de dez em dez segundos de propósito: o `currentTime` é
        observado continuamente lá dentro, e o que custa caro é atravessar as
        fronteiras. Quem consome extrapola entre um batimento e outro e corrige
        quando o próximo chega — está escrito na docstring de `index.js`, e
        esta função é a outra metade dessa decisão.

        Pausado não extrapola: o tempo passa, o filme não.
        """
        if self.currentTime is None or self.posicao_em is None:
            return None
        if not self.tocando:
            return self.currentTime
        projetada = self.currentTime + max(0.0, agora - self.posicao_em)
        # Passar do fim é sinal de que o batimento parou de chegar, não de que
        # a pessoa assistiu além do fim. Segurar no fim é mais honesto do que
        # devolver um número que não existe.
        if self.duration is not None and projetada > self.duration:
            return self.duration
        return projetada

    def posicao_do_adapter_agora(self, agora: float) -> float | None:
        """A mesma projeção, para o tempo que veio da PÁGINA.

        Duas funções e não uma com um parâmetro: são duas fontes com
        autoridades diferentes na tabela do Merger, e o dia em que uma delas
        precisar de regra própria — o Disney+ já quase precisou — misturá-las
        obrigaria a desfazer. O que elas compartilham é `posicao_em`, porque os
        dois números chegam no mesmo evento.
        """
        if self.adapterPosition is None or self.posicao_em is None:
            return None
        if not self.tocando:
            return self.adapterPosition
        projetada = self.adapterPosition + max(0.0, agora - self.posicao_em)
        if self.adapterDuration is not None and projetada > self.adapterDuration:
            return self.adapterDuration
        return projetada

    # ── O tempo que esta sessão conhece, sem passar pelo Merger ───────────
    #
    # `_da_ponte`, em `fusao.py`, monta o cartão direto quando o Windows não
    # tem leitura nenhuma — SMTC pendurada e janela sem título, que é o estado
    # medido desta máquina. Esse caminho não chama `fundir()`, então a ordem de
    # `FIELD_AUTHORITY` não o alcança.
    #
    # Estes dois espelham aquela ordem, e são o ÚNICO outro lugar que decide
    # entre as duas fontes de tempo. Se um terceiro aparecer, a duplicação
    # deixou de ser aceitável e o caminho de `_da_ponte` tem de passar a usar o
    # Merger de verdade.

    def melhor_posicao(self, agora: float) -> float | None:
        """A posição, com o adapter na frente. Mesma ordem do Merger."""
        do_adapter = self.posicao_do_adapter_agora(agora)
        return do_adapter if do_adapter is not None else self.posicao_agora(agora)

    @property
    def melhor_duracao(self) -> float | None:
        """A duração, com o adapter na frente. Mesma ordem do Merger."""
        return self.adapterDuration if self.adapterDuration is not None else self.duration


class EstadoDaPonte:
    """O que a extensão está dizendo, agora.

    Em memória e só em memória: isto descreve o instante, e um instante
    persistido em disco é um instante mentiroso na próxima vez que o servidor
    subir.
    """

    def __init__(self) -> None:
        self._sessoes: dict[str, SessaoDaPonte] = {}
        self._visto_em: float | None = None
        self._posicao_em: float | None = None

    # ── Entrada ───────────────────────────────────────────────────────────

    def registrar(self, evento: EventoDeMidia, agora: float | None = None) -> None:
        """Um evento validado entra. Chamado pela rota, uma vez por mensagem.

        `agora` é o relógio MONOTÔNICO do servidor, e não o `timestamp` do
        evento. O carimbo vem do relógio da aba, que pode estar torto — a
        própria validação tolera dez minutos de deriva. Medir frescor com um
        relógio que não é o nosso seria aceitar que a aba decida se o dado dela
        está fresco.
        """
        agora = time.monotonic() if agora is None else agora
        self._visto_em = agora

        if evento.messageType == "SESSION_ENDED":
            # A aba avisou que foi embora. Some agora, em vez de esperar o
            # prazo — o silêncio explicado é melhor do que o silêncio medido.
            self._sessoes.pop(evento.sessionId, None)
            return

        anterior = self._sessoes.get(evento.sessionId)

        # Fase 17 — mensagem fora de ordem.
        #
        # O content script numera cada mensagem da aba (`seq` em `index.js`), e
        # até aqui o backend ignorava o número por completo: o campo existia e
        # não era lido por ninguém.
        #
        # Sem ele, uma mensagem atrasada sobrescreve uma recente e a posição
        # anda PARA TRÁS sem nada ter acontecido na tela. É a mesma família do
        # `currentTime` congelado que a Fase 0 documentou: um número plausível
        # descrevendo um instante que já passou.
        #
        # Igual NÃO é fora de ordem — é reenvio, e reenviar o mesmo estado é
        # inofensivo. Só o que é MENOR se descarta.
        if (
            anterior is not None
            and anterior.ultimo_seq is not None
            and evento.seq is not None
            and evento.seq < anterior.ultimo_seq
        ):
            # A sessão continua VIVA: a aba falou, ainda que atrasado. Só o
            # conteúdo é que não vale.
            self._sessoes[evento.sessionId] = replace(anterior, visto_em=agora)
            return

        duracao_nova = _ou(evento.duration, anterior, "duration")
        posicao_em = anterior.posicao_em if anterior is not None else None
        if evento.currentTime is not None or evento.adapterPosition is not None:
            posicao_em = agora
            self._posicao_em = agora

        self._sessoes[evento.sessionId] = SessaoDaPonte(
            sessionId=evento.sessionId,
            tabId=_ou(evento.tabId, anterior, "tabId"),
            windowId=_ou(evento.windowId, anterior, "windowId"),
            platform=plataforma_do_host(evento.provider),
            # Campo a campo, herdando do anterior o que este evento não traz.
            # Um `PAUSE` sem duração não pode apagar a duração que o
            # `loadedmetadata` já tinha dito.
            playbackState=_ou(evento.playbackState, anterior, "playbackState"),
            currentTime=_ou(evento.currentTime, anterior, "currentTime"),
            duration=duracao_nova,
            playbackRate=_ou(evento.playbackRate, anterior, "playbackRate"),
            muted=_ou(evento.muted, anterior, "muted"),
            # `audible` NÃO herda: virou telemetria de aba na Fase 14, e é
            # sobre o instante. "Saía som há um minuto" não responde "sai som
            # agora?" — e essa resposta alimenta a política de consumo, onde
            # um `True` velho faria tempo de filme pausado contar.
            audible=evento.audible,
            workTitle=_ou(evento.workTitle, anterior, "workTitle"),
            episodeTitle=_ou(evento.episodeTitle, anterior, "episodeTitle"),
            seasonNumber=_ou(evento.seasonNumber, anterior, "seasonNumber"),
            episodeNumber=_ou(evento.episodeNumber, anterior, "episodeNumber"),
            pageId=_ou(evento.pageId, anterior, "pageId"),
            # Herdam, como o tempo do elemento: o overlay do Disney+ sai do DOM
            # depois de alguns segundos sem mouse, e nesses batimentos o
            # adapter projeta em cima da âncora. Quando nem projetar dá, o
            # último par conhecido continua sendo a melhor descrição — e o
            # frescor, que é outra pergunta, quem responde é `posicao_em`.
            adapterPosition=_ou(evento.adapterPosition, anterior, "adapterPosition"),
            adapterDuration=_ou(evento.adapterDuration, anterior, "adapterDuration"),
            documentTitle=_ou(evento.documentTitle, anterior, "documentTitle"),
            # A telemetria NÃO herda do evento anterior: ela descreve o
            # instante, e "a aba estava ativa há um minuto" não é resposta para
            # "a aba está ativa?". Herdar aqui produziria exatamente o tipo de
            # dado plausível-e-errado que a Fase 8 existe para recusar.
            active=evento.active,
            windowFocused=evento.windowFocused,
            tabMuted=evento.tabMuted,
            pictureInPicture=evento.pictureInPicture,
            visible=evento.visible,
            msDesdeUltimoPlay=evento.msDesdeUltimoPlay,
            msDesdeUltimoEvento=evento.msDesdeUltimoEvento,
            visto_em=agora,
            posicao_em=posicao_em,
            # Gruda: uma vez que a duração cresceu, ela é borda de buffer, e
            # continuar acreditando nela depois que ela parar seria acreditar
            # num número que já se provou não ser duração.
            duracao_cresceu=(
                (anterior.duracao_cresceu if anterior is not None else False)
                or _duracao_aumentou(anterior, duracao_nova)
            ),
            # Herdam: o retângulo do vídeo não muda entre batimentos, e um
            # evento que não o traga não pode apagar o alvo do clique.
            videoCentroX=_ou(evento.videoCentroX, anterior, "videoCentroX"),
            videoCentroY=_ou(evento.videoCentroY, anterior, "videoCentroY"),
            # O botão só existe enquanto os controles estão na tela, e some
            # depois de alguns segundos sem mouse. Herdar é o que permite
            # clicar nele quando ele não está visível AGORA — e ele volta para
            # o mesmo lugar, porque o player não o move.
            telaCheiaX=_ou(evento.telaCheiaX, anterior, "telaCheiaX"),
            telaCheiaY=_ou(evento.telaCheiaY, anterior, "telaCheiaY"),
            ultimo_seq=(
                evento.seq if evento.seq is not None
                else (anterior.ultimo_seq if anterior is not None else None)
            ),
        )
        self._esquecer_a_mesma_aba(self._sessoes[evento.sessionId])
        self._esquecer_fantasmas(self._sessoes[evento.sessionId])
        self._esquecer_velhas(agora)

    def _esquecer_velhas(self, agora: float) -> None:
        """Abas que pararam de falar saem. Sem isto o dicionário só cresce."""
        for chave, sessao in list(self._sessoes.items()):
            if (agora - sessao.visto_em) >= SEGUNDOS_ATE_DESCONECTAR:
                self._sessoes.pop(chave, None)

    def _esquecer_a_mesma_aba(self, nova: SessaoDaPonte) -> None:
        """Uma ABA tem uma sessão por vez. A nova encerra a anterior daquela aba.

        O manifesto declara `all_frames: false`, então cada aba carrega UM
        content script, e ele mantém UM `sessionId` de cada vez — ele o troca
        quando o `<video>` é trocado ou quando a página é recarregada. Nos dois
        casos o anterior acabou de verdade: não existe estado em que uma aba
        esteja tocando duas coisas.

        Sem isto a sessão anterior ficava viva até o prazo de cinco minutos,
        disputando com a atual. Medido em 26/08/2026, no diagnóstico ao vivo,
        com UMA aba do Prime Video aberta:

            tab=1826140783 PRIME_VIDEO pos=0.0    dur=None
                documentTitle='Prime Video: Watch movies, TV shows, ...'
            tab=1826140783 PRIME_VIDEO pos=1084.8 dur=1329.184
                documentTitle='Prime Video: Batman: The Animated Series: Volume 3'

        A primeira é a página inicial, de antes de a pessoa abrir o episódio. A
        `_esquecer_fantasmas` não a alcança: ela casa por serviço MAIS duração,
        e uma sessão que nunca chegou a ter duração não casa com nada. O
        sintoma que a pessoa vê é uma reprodução antiga reaparecendo depois de
        ela já ter fechado ou trocado — o "cache" que ela descreveu.

        A pergunta que esta regra responde é diferente da da outra, e por isso
        são duas: aquela pergunta "isto é a mesma reprodução?"; esta pergunta
        "isto veio do mesmo lugar?". Uma casa por conteúdo e precisa de
        duração; a outra casa por origem e não precisa de nada.
        """
        # Sem `tabId` não há origem a comparar. Ele vem do `sender` no service
        # worker, então é o Chrome afirmando — mas uma mensagem antiga, ou de um
        # caminho que não passou pelo worker, pode não o ter.
        if nova.tabId is None:
            return
        for chave, antiga in list(self._sessoes.items()):
            if chave == nova.sessionId:
                continue
            if antiga.tabId == nova.tabId:
                self._sessoes.pop(chave, None)

    def _esquecer_fantasmas(self, nova: SessaoDaPonte) -> None:
        """Duas sessões da MESMA reprodução: a mais nova substitui a anterior.

        O observador troca de `sessionId` quando o `<video>` é trocado — e a
        Netflix troca o elemento em mudança de qualidade, não só de episódio.
        A sessão anterior continuava viva no dicionário por cinco minutos,
        descrevendo a mesma coisa com um retrato velho.

        Medido em 26/08/2026: duas sessões da Netflix, ambas com
        `duration=8352.218875` — o mesmo filme —, uma sabendo o nome e a outra
        não. Elas disputavam entre si, o vencedor alternava a cada batimento, e
        o título piscava.

        "Mesma reprodução" é mesmo serviço E mesma duração ao segundo. Duas
        abas com o MESMO filme aberto ao mesmo tempo seriam fundidas por engano
        — e é o lado certo do erro: descrevem a mesma obra, e a mais recente é
        a que a pessoa está usando.
        """
        if nova.platform is None or nova.duration is None:
            return
        assinatura = (nova.platform, round(nova.duration))
        for chave, antiga in list(self._sessoes.items()):
            if chave == nova.sessionId or antiga.duration is None:
                continue
            if (antiga.platform, round(antiga.duration)) == assinatura:
                self._sessoes.pop(chave, None)

    # ── Saída ─────────────────────────────────────────────────────────────

    def saude(self, agora: float | None = None) -> SaudeDaPonte:
        agora = time.monotonic() if agora is None else agora
        desde_o_ultimo = None if self._visto_em is None else agora - self._visto_em
        return SaudeDaPonte(
            connected=(
                desde_o_ultimo is not None and desde_o_ultimo < SEGUNDOS_ATE_DESCONECTAR
            ),
            lastSeen=desde_o_ultimo,
            lastPositionUpdate=(
                None if self._posicao_em is None else agora - self._posicao_em
            ),
        )

    def vivas(self, agora: float | None = None) -> list[SessaoDaPonte]:
        """Todas as sessões que a ponte está observando agora.

        Fase 14: é o dataset. `atual` responde "qual delas vence"; esta
        responde "quais existem", que é a pergunta anterior — e a única que dá
        para fazer antes de haver política.
        """
        agora = time.monotonic() if agora is None else agora
        self._esquecer_velhas(agora)
        return [
            sessao for sessao in self._sessoes.values()
            if (agora - sessao.visto_em) < SEGUNDOS_ATE_DESCONECTAR
        ]

    def atual(self, agora: float | None = None) -> SessaoDaPonte | None:
        """A reprodução que a ponte está observando.

        Desde a Fase 15, quem decide é o `arbitro` — e ele decide com uma ordem
        que foi LIDA do dataset da Fase 14, não escrita de cabeça. Ver
        `bridge/arbitro.py` para os números que produziram cada critério.

        Esta docstring dizia, antes: "NÃO é o árbitro. O árbitro é a Fase 15, e
        ele vai precisar de audível, foco e aba ativa, que a ponte hoje não
        manda." Os três campos passaram a chegar na Fase 14, e é essa chegada
        que autorizou a troca.

        `_melhor` continua existindo e continua sendo usado por `atual_de`: as
        duas funções respondem perguntas diferentes. Aqui a pergunta é "qual
        aba a pessoa está assistindo?"; lá é "qual sessão descreve melhor este
        serviço?" — e a segunda não é sobre atenção, é sobre qualidade da
        leitura.
        """
        return escolher(self.vivas(agora))

    def atual_de(
        self, platform: Platform | None, agora: float | None = None,
    ) -> SessaoDaPonte | None:
        """A reprodução da ponte NAQUELE serviço.

        Existe porque perguntar "qual aba vence no geral?" e depois recusar a
        resposta por não ser do serviço certo é pior do que perguntar direito —
        e o "pior" foi medido, não suposto.

        Medido em 25/08/2026, com o dataset da Fase 14 na mão: 15 das 16
        observações eram `duas-tocando`, Netflix e YouTube ao mesmo tempo. O
        vencedor global alternava a cada batimento. Quando ele calhava de ser o
        YouTube, a fusão não casava com a Netflix, o título voltava a ser
        "Netflix", o gravador o descartava como genérico e ZERAVA o acumulador.
        Um filme inteiro assim nunca alcança os 90 segundos que o histórico
        exige — e o cartão não denunciava nada, porque cartão mostra instante e
        histórico precisa de continuidade.

        Isto NÃO é o árbitro da Fase 15. O árbitro responde "qual sessão é a
        ativa?" quando há várias candidatas legítimas. Aqui a pergunta já vinha
        com a resposta: quem quer saber já sabe de qual serviço está falando, e
        só precisava não ser atrapalhado pelas outras abas.
        """
        if platform is None:
            return None
        return self._melhor(
            [s for s in self.vivas(agora) if s.platform == platform],
        )

    @staticmethod
    def _melhor(sessoes: list[SessaoDaPonte]) -> SessaoDaPonte | None:
        """Qual reprodução responde por este serviço.

        A ordem, do critério mais forte para o mais fraco:

            1. tem IDENTIDADE de reprodução (`pageId`)
            2. está tocando
            3. falou por último

        O primeiro critério entrou em 25/08/2026, medido com o diagnóstico ao
        vivo e duas sessões da Netflix na mesma máquina:

            playing  pos=0.0/47.7    sem pageId    <- a vitrine da home
            paused   pos=222/8352    com pageId    <- Fight Club

        A vitrine da Netflix toca um trailer de quarenta segundos sozinha. Ela
        é um `<video>` de verdade, ela está mesmo tocando, e por "quem toca
        vence" ela ganhava do filme que a pessoa estava assistindo — que estava
        pausado justamente porque a pessoa foi olhar outra coisa.

        `pageId` separa os dois sem heurística de duração nem de tamanho: a
        vitrine não tem `/watch/<id>` na URL porque não é uma reprodução, é um
        enfeite da página. Ter identidade É a diferença entre "algo está
        tocando aqui" e "a pessoa está assistindo isto".

        NÃO é o árbitro da Fase 15. Aquele decide entre candidatas legítimas —
        duas obras de verdade, em abas diferentes — e precisa de foco, aba ativa
        e audível para isso. Aqui só se está tirando da disputa o que nunca foi
        candidato.
        """
        if not sessoes:
            return None
        return max(sessoes, key=lambda s: (
            s.pageId is not None,
            # Saber NOMEAR o que toca desempata antes da hora do último
            # batimento — e sem isto o desempate ficava instável.
            #
            # Medido em 26/08/2026, com o diagnóstico ao vivo:
            #
            #   NETFLIX paused pos=222.3/8352.218875  workTitle=None
            #   NETFLIX paused pos=305.3/8352.218875  workTitle='Fight Club'
            #
            # A MESMA duração: é o mesmo filme, visto por duas sessões — a viva
            # e o fantasma de quando o `<video>` foi trocado. Com as duas
            # paradas, o desempate caía em "quem falou por último", e as duas
            # batem: o vencedor ALTERNAVA a cada batimento.
            #
            # Cada alternância trocava o título entre "Fight Club" e o nome do
            # serviço (genérico, descartado), e o gravador zerava o acumulado.
            # Com batimento estrangulado em 60s, nunca chegava aos 120s que o
            # histórico exige. O cartão mostrava o filme certo o tempo todo, e o
            # histórico não crescia nunca.
            s.workTitle is not None,
            s.tocando,
            s.visto_em,
        ))

    def leituras(
        self, agora: float | None = None, platform: Platform | None = None,
    ) -> list[Leitura]:
        """As leituras que a ponte tem a oferecer ao Merger, agora.

        Lista vazia quando não há nada a declarar. `leitura` continua
        existindo para quem só quer a do elemento de mídia.
        """
        agora = time.monotonic() if agora is None else agora
        return [
            leitura for leitura in (
                self.leitura(agora, platform), self.leitura_do_adapter(agora, platform),
            )
            if leitura is not None
        ]

    def leitura_do_adapter(
        self, agora: float | None = None, platform: Platform | None = None,
    ) -> Leitura | None:
        """O que a PÁGINA declarou. `None` quando não há adapter.

        Metadata sempre; TEMPO quando o adapter souber medi-lo — e no Disney+
        ele é a única fonte que sabe, porque o `<video>` de lá reporta a janela
        DASH que está montando e não o episódio.

        Por isso esta leitura passou a ter `dinamicos_frescos`, e ele importa
        agora: nome de obra não está em `CAMPOS_DINAMICOS` e atravessa velho de
        propósito — o nome da obra de um minuto atrás continua sendo o nome da
        obra —, mas uma posição de um minuto atrás está errada agora. A mesma
        assimetria da Fase 8, dentro de uma fonte só.
        """
        agora = time.monotonic() if agora is None else agora
        sessao = self.atual_de(platform, agora) if platform else self.atual(agora)
        if sessao is None:
            return None

        campos: dict[str, MediaField] = {}

        def declarar(nome: str, valor: object) -> None:
            if valor is None:
                return
            # O adapter do serviço É autoridade para o nome da obra naquele
            # serviço — ele lê a página. Esta é a única fonte que pode nomear
            # uma obra na Netflix, e é a regra permanente do Master Loop:
            # "Netflix não pode depender de SMTC para metadata da obra."
            campos[nome] = MediaField(
                value=valor, source="provider-adapter", trustworthy=True,
            )

        declarar("workTitle", sessao.workTitle)
        declarar("episodeTitle", sessao.episodeTitle)
        declarar("seasonNumber", sessao.seasonNumber)
        declarar("episodeNumber", sessao.episodeNumber)
        # O tempo do adapter só é declarado quando ele existe. Um serviço cujo
        # `<video>` já sabe a posição — que é a regra, e a Netflix é o caso —
        # não manda estes campos, e aqui não há nada a declarar: o Merger
        # segue com `html-media-element`, como sempre.
        declarar("currentTime", sessao.posicao_do_adapter_agora(agora))
        declarar("duration", sessao.adapterDuration)

        if not campos:
            # Só o `pageId`, ou nem isso: nada a declarar ao Merger. Não
            # declarar é diferente de declarar vazio.
            return None
        return Leitura(
            fonte="provider-adapter",
            campos=campos,
            # Vale só para os campos dinâmicos. O nome da obra atravessa daqui
            # mesmo com o tempo velho, e é justamente essa a assimetria.
            dinamicos_frescos=(
                sessao.posicao_em is not None
                and (agora - sessao.posicao_em) < SEGUNDOS_ATE_O_TEMPO_ENVELHECER
            ),
        )

    def leitura(
        self, agora: float | None = None, platform: Platform | None = None,
    ) -> Leitura | None:
        """O que a ponte declara, na forma que o Merger entende.

        `None` quando não há nada a declarar — diferente de declarar vazio, e a
        diferença importa: o Merger não deve receber uma fonte que não falou.

        DUAS leituras, e não uma, porque são duas fontes diferentes com
        autoridades diferentes na tabela do Merger:

            html-media-element   tempo e estado técnico. Envelhece.
            provider-adapter     obra, episódio, temporada. NÃO envelhece.

        A assimetria é a mesma da Fase 8, e agora ela tem consequência prática:
        quando a aba para de mandar posição, o tempo dela sai da disputa e o
        NOME continua valendo. O nome da obra de um minuto atrás continua sendo
        o nome da obra.
        """
        agora = time.monotonic() if agora is None else agora
        sessao = self.atual_de(platform, agora) if platform else self.atual(agora)
        if sessao is None:
            return None

        posicao = sessao.posicao_agora(agora)
        campos: dict[str, MediaField] = {}

        def declarar(nome: str, valor: object) -> None:
            # `trustworthy` diz que o `<video>` da página É autoridade para
            # tempo e estado técnico — ele está lá dentro. Isto é CAPACIDADE, e
            # ela não muda com o relógio. Se o dado envelheceu, quem barra é o
            # `dinamicos_frescos` abaixo, não este booleano. Misturar os dois é
            # exatamente o que a Fase 8 existe para separar.
            campos[nome] = MediaField(
                value=valor, source="html-media-element", trustworthy=valor is not None,
            )

        declarar("currentTime", posicao)
        declarar("duration", sessao.duration)
        declarar("playbackState", sessao.playbackState)
        declarar("playbackRate", sessao.playbackRate)
        declarar("muted", sessao.muted)
        declarar("audible", sessao.audible)

        return Leitura(
            fonte="html-media-element",
            campos=campos,
            # A ponte pode estar CONECTADA e com o tempo velho ao mesmo tempo:
            # é o caso de uma aba que ficou pendurada sem mandar posição nova.
            # Aí ela some da disputa pelos campos dinâmicos e a SMTC assume.
            dinamicos_frescos=(
                sessao.posicao_em is not None
                and (agora - sessao.posicao_em) < SEGUNDOS_ATE_O_TEMPO_ENVELHECER
            ),
        )


#: Quanto a duração precisa subir para contar como crescimento.
#:
#: Meio segundo: as casas decimais do MSE oscilam entre leituras da mesma
#: reprodução, e um limite de zero acusaria toda oscilação como buffer.
FOLGA_DA_DURACAO = 0.5


def _duracao_aumentou(anterior: SessaoDaPonte | None, nova: float | None) -> bool:
    """A duração subiu desde a leitura anterior?

    Só SUBIR conta. Uma duração que desce é troca de reprodução — o episódio
    seguinte, mais curto — e isso já é tratado pela identidade da reprodução.
    """
    if anterior is None or anterior.duration is None or nova is None:
        return False
    return nova - anterior.duration > FOLGA_DA_DURACAO


def _ou(valor: object, anterior: SessaoDaPonte | None, campo: str) -> object:
    """Este evento respondeu? Senão, vale o que a sessão já sabia."""
    if valor is not None:
        return valor
    return getattr(anterior, campo) if anterior is not None else None


#: A instância que a rota alimenta e o Dispatcher lê.
#:
#: Módulo-nível pela mesma razão que `websocket.dispatcher` é: as duas rotas
#: sobem no mesmo processo e precisam do MESMO objeto. Injetável nos dois lados
#: para que o teste nunca dependa deste singleton.
estado_da_ponte = EstadoDaPonte()
