"""O Merger entrando no caminho de leitura de produção.

A Fase 7 escreveu `fundir()` e o deixou de fora: "o Merger ainda NÃO está no
caminho de leitura de produção. Ele entra quando houver frescor para
alimentá-lo — Fase 8." O frescor existe (`bridge/estado.py`). Este módulo é a
ligação, e ele é só isso: traduz o que a leitura de produção já sabe para a
linguagem do Merger, chama `fundir()`, e traduz o resultado de volta.

## O que é decidido aqui, e o que não é

Decidido aqui: nada. A ordem de autoridade mora em `FIELD_AUTHORITY`, o frescor
mora na `Leitura`, e a capacidade mora no `trustworthy` de cada `MediaField`.
Se um dia este arquivo ganhar um `if` que escolha fonte, o critério de
implementação incorreta nº 5 do Master Loop foi violado.

## Quem disputa o quê

    currentTime, duration    html-media-element  →  smtc
    playbackState            html-media-element  →  smtc
    workTitle, episodeTitle  provider-adapter    →  smtc/janela

A terceira linha entrou na **Fase 10**, e é a que dá nome à Netflix. Até ela
existir, `workTitle` tinha uma fonte só e passar por aqui devolveria o mesmo
valor com mais cerimônia. Agora há disputa de verdade — e o adapter vence,
porque ele lê a página.

A assimetria de frescor continua valendo e agora tem consequência prática: se a
aba parar de mandar posição, o TEMPO dela sai da disputa e o NOME continua.
O nome da obra de um minuto atrás continua sendo o nome da obra.

## O casamento de serviço, que não é detalhe

A ponte fala em `location.hostname`; o resto do sistema fala em `Platform`. Se
os dois não baterem, o tempo NÃO é aplicado. Sem essa checagem, uma aba da
Netflix aberta atrás carimbaria a linha do tempo do filme que está tocando no
Prime Video — e o número caberia na duração, pareceria plausível, e seria de
outra coisa. É o mesmo modo de falha que o `RelogioDaMidia` existe para pegar
na SMTC, só que vindo pelo outro lado.
"""

from __future__ import annotations

from dataclasses import replace
import time

from app.bridge.contratos import MediaField
from app.bridge.estado import EstadoDaPonte
from app.bridge.merger import Leitura, fundir
from app.media.identidade import identidade_da_reproducao
from app.commands.parser import PLATFORM_LABELS
from app.media.now_playing import (
    PLATAFORMAS_COM_OBRA_NA_JANELA,
    NowPlaying,
    _titulo_generico,
    limpar_titulo_de_janela,
    obra_e_episodio_do_titulo,
)


#: Os campos dinâmicos que a fusão resolve. Ver a docstring do módulo.
CAMPOS_FUNDIDOS = ("currentTime", "duration", "playbackState", "muted")

#: Os campos de identidade. Separados porque não envelhecem junto com o tempo.
CAMPOS_DE_METADATA = ("workTitle", "episodeTitle", "seasonNumber", "episodeNumber")


def leitura_da_smtc(atual: NowPlaying) -> Leitura:
    """O que a leitura do Windows declara, na linguagem do Merger.

    `dinamicos_frescos` sai de `position_stale`, que é a conclusão que o
    `RelogioDaMidia` já produz: "este número é desta reprodução, mas parou de
    ser atualizado". Traduzir em vez de remedir é de propósito — o
    `RelogioDaMidia` conhece três estados e já custou caro para acertar.
    """
    def campo(valor: object) -> MediaField:
        return MediaField(
            value=valor, source="smtc", trustworthy=valor is not None,
        )

    campos = {
        "currentTime": campo(atual.position_seconds),
        "duration": campo(atual.duration_seconds),
        "playbackState": campo("playing" if atual.playing else "paused"),
        "muted": campo(None),
    }
    # O título entra na disputa com a CAPACIDADE que a leitura já apurou:
    # `trustworthy` é "este nome é o da OBRA", e é ele que distingue "Ben 10"
    # de "Fame". Um nome de episódio entrando como se fosse obra é o bug que
    # `PLATAFORMAS_COM_OBRA_NA_JANELA` existe para impedir, e ele continua
    # impedindo aqui.
    campos["workTitle"] = MediaField(
        value=atual.title or None, source="smtc", trustworthy=atual.trustworthy,
    )
    campos["episodeTitle"] = MediaField(
        value=atual.episode, source="smtc", trustworthy=atual.episode is not None,
    )
    return Leitura(fonte="smtc", campos=campos, dinamicos_frescos=not atual.position_stale)


def _episodio_legivel(sessao) -> str | None:
    """"T2 E1 · Um Escândalo", quando a página publicou os números.

    O formato não é decorativo: `como_temporada_e_episodio`, no histórico, lê
    exatamente "T2 E1" para montar a linha da tela de perfil. Escrever de outro
    jeito faria os números chegarem e não serem lidos.
    """
    partes = []
    if sessao.seasonNumber is not None:
        partes.append(f"T{sessao.seasonNumber}")
    if sessao.episodeNumber is not None:
        partes.append(f"E{sessao.episodeNumber}")
    numeros = " ".join(partes) or None

    # A temporada aparece SÓ quando ela é conhecida — nunca inferida.
    #
    # A Netflix escreve "E1" sozinho quando já se sabe em que temporada se
    # está, e ali a temporada não existe no que a página publicou. Preencher com
    # "T1" seria um palpite, e o palpite fica errado exatamente para quem mais
    # precisa da informação: quem está na quinta temporada.
    #
    # É a mesma regra de `temporada_e_episodio` no backend, e a razão dela vale
    # aqui inteira: um "T1 E1" inventado é pior do que "E1", porque a pessoa
    # acredita nele.
    nome = sessao.episodeTitle
    if numeros is not None and nome is not None:
        return f"{numeros} · {nome}"
    return numeros or nome


def _nome_da_aba(sessao) -> str | None:
    """O título da aba, limpo pelo MESMO limpador da janela.

    É a mesma string: "Prime Video: Invincible", "⁨46 Long⁩ • HBO Max". O que
    muda é de onde ela vem — da aba, que a tem sempre, em vez da janela, que só
    a publica quando a aba está na frente.

    Reusar `limpar_titulo_de_janela` não é economia: ele conhece o formato de
    cada serviço, custou caro para acertar (o "(2)" do Chrome, os invisíveis do
    Max, o "Prime Video:" na frente, o "(Não está respondendo)" do Windows) e
    tem teste para cada caso. Escrever um segundo limpador seria criar uma
    segunda verdade sobre a mesma string.
    """
    if not sessao.documentTitle:
        return None
    limpo = limpar_titulo_de_janela(sessao.documentTitle).strip()
    if not limpo or _titulo_generico(limpo, None, sessao.platform):
        return None
    return limpo


def _episodio_da_aba(sessao) -> str | None:
    """O episódio quando ele vem dentro do título da aba.

    Prime Video e Disney+ publicam obra e episódio na MESMA string
    ("Invincible - S1 E4 - Neil Armstrong"). Sem isto, o adapter da Netflix era
    a única forma de o episódio chegar — e por isso só ela gravava T/E.
    """
    if not sessao.documentTitle:
        return None
    return obra_e_episodio_do_titulo(sessao.documentTitle)[1]


def _da_ponte(estado: EstadoDaPonte, agora: float | None) -> NowPlaying | None:
    """Uma leitura construída SÓ com o que a página disse.

    O nome vem de duas fontes, nesta ordem:

        adapter do serviço      Netflix. Obra, episódio, temporada. É a fonte de
                                maior autoridade, e a única que sabe separar as
                                três coisas.

        título da ABA           todos os outros. É a MESMA string que a janela
                                do Chrome publica, e o mesmo limpador a trata —
                                só que a aba a tem SEMPRE, e a janela só quando
                                ela está na frente.

    A segunda entrou em 26/08/2026, medida como falta: com a aba em segundo
    plano, Prime Video, Disney+, Max e YouTube não capturavam nada. A janela
    publica o título da aba ATIVA, e a pessoa que troca de aba some do próprio
    controle. Só a Netflix escapava, e só porque tem adapter.

    Quem NOMEIA a obra e quem nomeia o episódio continua sendo decidido por
    `PLATAFORMAS_COM_OBRA_NA_JANELA` — a mesma tabela de sempre, porque é a
    mesma string. O Max continua publicando o episódio, e continua não valendo
    como obra.

    Sem serviço reconhecido não há nada a dizer. Um `<video>` numa página
    qualquer não é mídia que este controle opere.
    """
    sessao = estado.atual(agora)
    if sessao is None or sessao.platform is None:
        return None
    # Nada tocando e nada pausado com posição: não há reprodução a descrever.
    if sessao.playbackState is None:
        return None

    da_aba = _nome_da_aba(sessao)
    nome = sessao.workTitle or da_aba
    # O adapter afirma obra; a aba afirma o que a tabela de capacidade permitir.
    tem_nome = sessao.workTitle is not None or (
        da_aba is not None and sessao.platform in PLATAFORMAS_COM_OBRA_NA_JANELA
    )
    return NowPlaying(
        title=nome or PLATFORM_LABELS.get(sessao.platform, sessao.platform),
        artist=None,
        app=None,
        platform=sessao.platform,
        playing=sessao.tocando,
        # `melhor_*` e não `posicao_agora`: no Disney+ o `<video>` reporta a
        # janela DASH que está montando, e não o episódio. Medido, no mesmo
        # instante: 50.8 no elemento contra 146 no player, com `duration`
        # valendo `Infinity`. A ordem é a mesma de `FIELD_AUTHORITY` — este
        # caminho não passa pelo Merger, e a docstring de `melhor_posicao`
        # explica por que a duplicação é tolerada aqui e em nenhum outro lugar.
        position_seconds=sessao.melhor_posicao(
            agora if agora is not None else time.monotonic(),
        ),
        duration_seconds=sessao.melhor_duracao,
        thumbnail=None,
        # O adapter primeiro; o título da aba quando não há adapter.
        episode=_episodio_legivel(sessao) or _episodio_da_aba(sessao),
        # Só o adapter nomeia obra. Sem ele, o título é o do serviço — e dizer
        # que aquilo é a obra poria "Prime Video" no histórico como filme.
        trustworthy=tem_nome,
        ended=sessao.playbackState == "ended",
        playback_id=identidade_da_reproducao(
            sessao.pageId, sessao.seasonNumber, sessao.episodeNumber,
            sessao.episodeTitle, sessao.melhor_duracao,
        ),
    )


def fundir_com_a_ponte(
    atual: NowPlaying | None,
    estado: EstadoDaPonte,
    agora: float | None = None,
) -> NowPlaying | None:
    """A leitura do Windows, com o tempo da ponte quando ele for melhor.

    Devolve `atual` intacto quando a ponte não tem nada a dizer — que é o
    estado normal de quem não instalou a extensão, e o caminho que garante que
    esta fase não regride Spotify, Max, Disney+, Prime Video nem YouTube.
    """
    if atual is None:
        # Nenhuma leitura do Windows — e a ponte pode saber tudo mesmo assim.
        #
        # Medido em 25/08/2026 com o diagnóstico ao vivo: a SMTC desta máquina
        # está pendurada e NUNCA respondeu (`lastSuccess: null`), e a janela do
        # Chrome publica o título da aba ATIVA — que era o DevTools. As duas
        # fontes do Windows cegas ao mesmo tempo, enquanto a ponte reportava
        # `PRIME_VIDEO playing pos=1045/3029`.
        #
        # Enriquecer o nada dava nada. A ponte precisa poder falar sozinha.
        return _da_ponte(estado, agora)

    # A sessão DESTE serviço, e não "a que vence no geral". Com duas abas
    # tocando ao mesmo tempo — o estado mais comum no dataset da Fase 14 — o
    # vencedor global alterna a cada batimento, e cada alternância derrubava a
    # fusão da Netflix. Ver `EstadoDaPonte.atual_de`.
    sessao = estado.atual_de(atual.platform, agora)
    if sessao is None:
        return atual

    leituras = estado.leituras(agora, atual.platform)
    if not leituras:
        return atual

    fundida = fundir([*leituras, leitura_da_smtc(atual)])
    procedencia = fundida.procedencia()

    veio_tempo = any(procedencia[c] == "html-media-element" for c in CAMPOS_FUNDIDOS)
    veio_nome = any(procedencia[c] == "provider-adapter" for c in CAMPOS_DE_METADATA)

    # Fase 13 — a ponte parou de mandar posição e ninguém assumiu.
    #
    # Na Netflix a SMTC nunca teve posição, então "ninguém assumiu" é o estado
    # NORMAL quando a extensão envelhece. Sem esta rede a posição vira `None`, a
    # barra some inteira e o cartão volta a ser um cartaz no meio do filme.
    #
    # Tem de ser avaliado ANTES do retorno antecipado abaixo: uma ponte velha
    # não oferece campo nenhum ao Merger, então ela cairia justamente no "nada
    # veio da ponte" — e o caso que a rede existe para cobrir nunca chegaria a
    # ela.
    parada_da_ponte = (
        not fundida.currentTime.utilizavel and sessao.currentTime is not None
    )

    # Nada veio da ponte: devolver o original preserva `position_stale` e tudo
    # o mais exatamente como estava.
    if not veio_tempo and not veio_nome and not parada_da_ponte:
        return atual

    # O nome da OBRA veio do adapter: ele lê a página, então é o nome certo, e
    # `trustworthy` passa a ser verdade por construção. É a regra permanente do
    # Master Loop virando código — "Netflix não pode depender de SMTC para
    # metadata da obra".
    titulo = atual.title
    episodio = atual.episode
    confiavel = atual.trustworthy
    if procedencia["workTitle"] == "provider-adapter" and fundida.workTitle.utilizavel:
        titulo = fundida.workTitle.value
        confiavel = True
    if veio_nome:
        episodio = _episodio_legivel(sessao) or episodio

    # Fase 11: a identidade da REPRODUÇÃO, do sinal mais forte que houver.
    # O `pageId` é o mais forte de todos — é a própria Netflix dizendo qual
    # reprodução é, sem depender de nome nem de duração.
    reproducao = identidade_da_reproducao(
        sessao.pageId, sessao.seasonNumber, sessao.episodeNumber,
        sessao.episodeTitle, sessao.duration,
    )

    posicao = fundida.currentTime
    estado_da_reproducao = fundida.playbackState

    # O último valor que a ponte mediu, SEM extrapolar. É a mesma distinção de
    # três estados que o `RelogioDaMidia` já faz com a SMTC:
    #
    #     VIVA      a posição anda: vale projetar daqui.
    #     PARADA    o número é desta reprodução e parou de ser atualizado.
    #               Vale mostrar; não vale avançar sozinho.
    #     SUSPEITA  o número é de outra reprodução: não vale nada.
    #
    # Aqui não há SUSPEITA: a sessão da ponte é identificada por `sessionId`, e
    # ela some quando a reprodução acaba. O número velho é sempre desta.
    #
    # Projetar seria a "dupla estimativa" que o gate proíbe — duas fontes
    # inventando avanço sobre o mesmo número.
    if parada_da_ponte:
        return replace(
            atual,
            title=titulo,
            episode=episodio,
            trustworthy=confiavel,
            playback_id=reproducao or atual.playback_id,
            position_seconds=sessao.currentTime,
            duration_seconds=sessao.duration or atual.duration_seconds,
            # Marcado como parado: quem desenha não o faz avançar sozinho.
            position_stale=True,
        )

    return replace(
        atual,
        title=titulo,
        episode=episodio,
        trustworthy=confiavel,
        playback_id=reproducao or atual.playback_id,
        position_seconds=posicao.value if posicao.utilizavel else atual.position_seconds,
        duration_seconds=(
            fundida.duration.value if fundida.duration.utilizavel
            else atual.duration_seconds
        ),
        playing=(
            estado_da_reproducao.value == "playing" if estado_da_reproducao.utilizavel
            else atual.playing
        ),
        # "Acabou" é diferente de "pausado", e só a ponte sabe a diferença. A
        # SMTC publica "pausado" nos dois casos — e é por isso que um filme
        # terminado nunca saía de "continuar assistindo".
        ended=(
            estado_da_reproducao.value == "ended" if estado_da_reproducao.utilizavel
            else atual.ended
        ),
        # A ponte respondendo pela posição significa que ela é fresca — o
        # `dinamicos_frescos` da `Leitura` já barrou o contrário. "Parada" é uma
        # afirmação sobre a SMTC, e ela deixou de ser quem responde.
        position_stale=(
            atual.position_stale if procedencia["currentTime"] != "html-media-element"
            else False
        ),
    )
