"""Fase 8 — Source Availability / Freshness.

O gate desta fase tem três frases, e as três são sobre a mesma confusão:

    Fonte morta não fornece estado dinâmico.
    Window Title recente não vira automaticamente confiável.
    Capability != freshness.

Capacidade é "esta fonte SABE responder este campo neste serviço". Frescor é "o
que ela disse ainda descreve o agora". São perguntas diferentes, e nenhuma das
duas responde pela outra.
"""

from __future__ import annotations

import pytest

from app.bridge.estado import (
    SEGUNDOS_ATE_DESCONECTAR,
    SEGUNDOS_ATE_O_TEMPO_ENVELHECER,
    EstadoDaPonte,
    plataforma_do_host,
)
from app.bridge.eventos import EventoDeMidia
from app.media.fusao import fundir_com_a_ponte
from app.media.now_playing import NowPlaying


def evento(
    messageType: str = "POSITION_SYNC",
    sessionId: str = "sessao-1",
    provider: str | None = "www.netflix.com",
    playbackState: str | None = "playing",
    currentTime: float | None = 100.0,
    duration: float | None = 3238.0,
    **extra: object,
) -> EventoDeMidia:
    campos: dict = {
        "messageType": messageType,
        "sessionId": sessionId,
        "tabId": None,
        "windowId": None,
        "provider": provider,
        "playbackState": playbackState,
        "currentTime": currentTime,
        "duration": duration,
        "playbackRate": 1.0,
        "audible": None,
        "muted": None,
        "timestamp": 0.0,
    }
    campos.update(extra)
    return EventoDeMidia(**campos)


def sessao_smtc(**overrides: object) -> NowPlaying:
    campos: dict = {
        "title": "Duna",
        "artist": None,
        "app": "chrome.exe",
        "platform": "NETFLIX",
        "playing": True,
        "position_seconds": 10.0,
        "duration_seconds": 3238.0,
        "thumbnail": None,
    }
    campos.update(overrides)
    return NowPlaying(**campos)


# ── Hostname → serviço ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("host", "esperado"),
    [
        ("www.netflix.com", "NETFLIX"),
        ("netflix.com", "NETFLIX"),
        ("play.hbomax.com", "MAX"),
        ("www.disneyplus.com", "DISNEY_PLUS"),
        ("www.primevideo.com", "PRIME_VIDEO"),
        ("www.youtube.com", "YOUTUBE"),
        # Um site qualquer não é serviço nenhum, e o tempo dele não carimba
        # a linha do tempo de coisa alguma.
        ("exemplo.com", None),
        # E o sufixo não pode casar por acaso: "naonetflix.com" não é Netflix.
        ("naonetflix.com", None),
        (None, None),
        ("", None),
    ],
)
def test_o_servico_por_tras_do_hostname(host, esperado):
    assert plataforma_do_host(host) == esperado


# ── Saúde da ponte ────────────────────────────────────────────────────────

def test_ponte_que_nunca_falou_nao_esta_conectada():
    saude = EstadoDaPonte().saude(agora=100.0)

    assert saude.connected is False
    # `None` é "nunca falou", que é diferente de "falou há muito tempo".
    assert saude.lastSeen is None
    assert saude.lastPositionUpdate is None


def test_a_saude_separa_falar_de_mexer_a_posicao():
    """Uma aba pausada continua batendo sem mexer a posição.

    Chamar isso de "desconectada" apagaria a informação de que a extensão está
    lá; chamar a posição de fresca seria pior. São dois números por isso.
    """
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=100.0), agora=0.0)
    estado.registrar(evento(messageType="PAUSE", currentTime=None), agora=30.0)

    saude = estado.saude(agora=30.0)

    assert saude.connected is True
    assert saude.lastSeen == 0.0
    assert saude.lastPositionUpdate == 30.0


def test_o_silencio_longo_desconecta():
    estado = EstadoDaPonte()
    estado.registrar(evento(), agora=0.0)

    assert estado.saude(agora=SEGUNDOS_ATE_DESCONECTAR + 1).connected is False


# ── Gate: fonte morta não fornece estado dinâmico ─────────────────────────

def test_fonte_morta_nao_fornece_estado_dinamico():
    """A frase literal do gate.

    A ponte falou há muito tempo. O que ela disse continua sendo verdade sobre
    o passado e não é mais verdade sobre agora, então ela sai da disputa.
    """
    estado = EstadoDaPonte()
    estado.registrar(evento(), agora=0.0)

    leitura = estado.leitura(agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 1)

    assert leitura is not None
    assert leitura.dinamicos_frescos is False
    # E "não fornece" é literal: o Merger não recebe oferta nenhuma dela.
    assert leitura.oferta("currentTime") is None
    assert leitura.oferta("playbackState") is None


def test_fonte_morta_nao_rouba_a_posicao_da_smtc():
    """O mesmo, agora pelo lado do resultado: a SMTC continua respondendo."""
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=2974.0), agora=0.0)

    fundida = fundir_com_a_ponte(
        sessao_smtc(position_seconds=10.0),
        estado,
        agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 1,
    )

    assert fundida.position_seconds == 10.0


# ── Gate: capability != freshness ─────────────────────────────────────────

def test_capacidade_nao_e_frescor():
    """A ponte é autoridade para tempo SEMPRE, e fresca só às vezes.

    O `trustworthy` de cada campo responde "esta fonte sabe medir isto?" e não
    muda com o relógio — o `<video>` da página não deixa de ser quem mede o
    tempo porque o batimento atrasou. Quem muda com o relógio é o
    `dinamicos_frescos`. Guardar as duas respostas no mesmo booleano é o erro
    que esta fase existe para travar.
    """
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=100.0), agora=0.0)

    fresca = estado.leitura(agora=1.0)
    velha = estado.leitura(agora=SEGUNDOS_ATE_O_TEMPO_ENVELHECER + 1)

    # A capacidade é a mesma nas duas.
    assert fresca.campos["currentTime"].trustworthy is True
    assert velha.campos["currentTime"].trustworthy is True
    # O frescor não.
    assert fresca.dinamicos_frescos is True
    assert velha.dinamicos_frescos is False


def test_window_title_recente_nao_vira_confiavel():
    """A frase literal do gate, e o caso do Max.

    A janela foi lida agora mesmo. Ela continua não sendo autoridade para o
    nome da obra no Max — ela publica o EPISÓDIO, sempre, e ler de novo não
    promove ninguém. Capacidade não é frescor.

    O exemplo era a Netflix até 25/08/2026, quando se mediu que a página de
    REPRODUÇÃO dela publica a obra. O Max continua sendo o caso puro: lá o
    valor está certo e a AFIRMAÇÃO "isto é a obra" é que seria falsa.
    """
    from app.media.now_playing import PLATAFORMAS_COM_OBRA_NA_JANELA, da_janela

    agora_mesmo = da_janela("⁨46 Long⁩ • HBO Max - Google Chrome", "MAX", tocando=True)

    assert "MAX" not in PLATAFORMAS_COM_OBRA_NA_JANELA
    assert agora_mesmo.trustworthy is False
    # E o nome continua na tela: ele é a única pista do que está tocando.
    assert agora_mesmo.title == "46 Long"


# ── A fusão ───────────────────────────────────────────────────────────────

def test_a_ponte_fresca_responde_pela_posicao():
    """O conserto medido: o número bom deixa de ser descartado.

    Em 25/08/2026 o `host.log` registrou `currentTime=2974.46 duration=3238` e
    o histórico gravou `posicao 391.03 / 3238.0` na mesma sessão. A duração
    batia; a posição estava dois mil e quinhentos segundos atrás.
    """
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=2974.46, duration=3238.0), agora=0.0)

    fundida = fundir_com_a_ponte(
        sessao_smtc(position_seconds=391.03, duration_seconds=3238.0),
        estado,
        agora=0.0,
    )

    assert fundida.position_seconds == pytest.approx(2974.46)
    assert fundida.position_stale is False


def test_a_posicao_da_ponte_e_extrapolada_entre_batimentos():
    """O batimento é de dez em dez segundos, e o cartão anda a cada volta.

    Sem extrapolar, a barra andaria aos saltos de dez em dez — que é
    exatamente a "sensação de cartaz" que este trabalho começou a consertar.
    """
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=100.0), agora=0.0)

    fundida = fundir_com_a_ponte(sessao_smtc(), estado, agora=7.0)

    assert fundida.position_seconds == pytest.approx(107.0)


def test_pausado_nao_extrapola():
    """O tempo passa, o filme não.

    Dentro do prazo de frescor de propósito: uma aba pausada CONTINUA batendo
    de dez em dez segundos (o relógio de `index.js` não pergunta se está
    tocando), então ela não envelhece por estar parada. Envelhecer aqui seria
    testar a outra coisa, que já tem teste próprio.
    """
    estado = EstadoDaPonte()
    estado.registrar(
        evento(messageType="PAUSE", playbackState="paused", currentTime=100.0),
        agora=0.0,
    )

    fundida = fundir_com_a_ponte(sessao_smtc(), estado, agora=20.0)

    assert fundida.position_seconds == pytest.approx(100.0)
    assert fundida.playing is False


def test_a_ponte_faz_o_pausado_chegar_ao_cartao():
    """Na Netflix o `playing` da SMTC nunca vira `false`. Pela ponte, vira.

    É a metade de servidor do botão que não mudava de pause para play.
    """
    estado = EstadoDaPonte()
    estado.registrar(
        evento(messageType="PAUSE", playbackState="paused", currentTime=100.0),
        agora=0.0,
    )

    fundida = fundir_com_a_ponte(sessao_smtc(playing=True), estado, agora=0.0)

    assert fundida.playing is False


def test_a_ponte_de_outro_servico_nao_carimba_a_sessao():
    """Uma aba da Netflix aberta atrás não descreve o Prime Video da frente.

    O número caberia na duração e pareceria plausível — é o mesmo modo de falha
    que o `RelogioDaMidia` pega na SMTC, vindo pelo outro lado.
    """
    estado = EstadoDaPonte()
    estado.registrar(evento(provider="www.netflix.com", currentTime=2974.0), agora=0.0)

    fundida = fundir_com_a_ponte(
        sessao_smtc(platform="PRIME_VIDEO", position_seconds=10.0), estado, agora=0.0,
    )

    assert fundida.position_seconds == 10.0


def test_sem_ponte_nada_muda():
    """Quem não instalou a extensão não perde nada.

    É o teste que sustenta as cinco regras de não-regressão do Master Loop:
    Spotify, Max, Disney+, Prime Video e YouTube seguem pelo caminho de antes.
    """
    antes = sessao_smtc(position_seconds=42.0, playing=True)

    assert fundir_com_a_ponte(antes, EstadoDaPonte(), agora=0.0) is antes


def test_a_ponte_sozinha_produz_uma_leitura():
    """As duas fontes do Windows podem estar cegas ao mesmo tempo.

    Medido em 25/08/2026 com o diagnóstico ao vivo: a SMTC desta máquina está
    pendurada e nunca respondeu, e a janela do Chrome publica o título da aba
    ATIVA — que era o DevTools. Enriquecer o nada dava nada, e a ponte sabia
    tudo: `PRIME_VIDEO playing pos=1045/3029`.
    """
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=1045.0, duration=3029.0), agora=0.0)

    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    assert lida is not None
    assert lida.platform == "NETFLIX"
    assert lida.position_seconds == pytest.approx(1045.0)
    assert lida.playing is True
    # Sem adapter não há nome de obra, e o serviço não é uma obra.
    assert lida.trustworthy is False


def test_a_ponte_sozinha_com_adapter_vale_como_obra():
    """Com o adapter, a ponte nomeia — e aí vale para o histórico."""
    estado = EstadoDaPonte()
    estado.registrar(
        evento(workTitle="Spider-Man: Across the Spider-Verse", currentTime=100.0),
        agora=0.0,
    )

    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    assert lida.title == "Spider-Man: Across the Spider-Verse"
    assert lida.trustworthy is True


def test_sem_servico_reconhecido_a_ponte_nao_inventa_leitura():
    """Um `<video>` numa página qualquer não é mídia que este controle opere."""
    estado = EstadoDaPonte()
    estado.registrar(evento(provider="exemplo.com"), agora=0.0)

    assert fundir_com_a_ponte(None, estado, agora=0.0) is None


def test_sem_ponte_e_sem_windows_continua_sem_midia():
    assert fundir_com_a_ponte(None, EstadoDaPonte(), agora=0.0) is None


# ── Sessões ───────────────────────────────────────────────────────────────

def test_a_sessao_herda_o_que_o_evento_novo_nao_traz():
    """Um `PAUSE` sem duração não apaga a duração que já se sabia."""
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=100.0, duration=3238.0), agora=0.0)
    estado.registrar(
        evento(messageType="PAUSE", playbackState="paused", currentTime=None, duration=None),
        agora=1.0,
    )

    assert estado.atual(agora=1.0).duration == 3238.0


def test_a_aba_que_toca_vence_a_aba_parada():
    """Duas abas abertas é o estado normal: o serviço num lugar, o catálogo em
    outro. Sem desempate, a última a falar venceria — e a última a falar é
    frequentemente a que não está tocando."""
    estado = EstadoDaPonte()
    # Durações diferentes de propósito: são reproduções diferentes. Com a mesma
    # duração elas seriam a MESMA reprodução vista duas vezes, e a mais nova
    # substituiria a anterior — ver `_esquecer_fantasmas`.
    estado.registrar(
        evento(sessionId="tocando", playbackState="playing", duration=3238.0), agora=0.0,
    )
    estado.registrar(
        evento(sessionId="parada", playbackState="paused", duration=5000.0), agora=1.0,
    )

    assert estado.atual(agora=1.0).sessionId == "tocando"


def test_a_sessao_encerrada_some_na_hora():
    estado = EstadoDaPonte()
    estado.registrar(evento(), agora=0.0)
    estado.registrar(evento(messageType="SESSION_ENDED"), agora=1.0)

    assert estado.atual(agora=1.0) is None


def test_a_troca_de_episodio_troca_de_sessao():
    """Medido no `host.log`: a duração pulou de 3238 para 2921 e o tempo voltou
    a zero. A extensão trocou o `sessionId` sozinha, e a duração nova não pode
    herdar nada da reprodução que acabou."""
    estado = EstadoDaPonte()
    estado.registrar(
        evento(sessionId="ep1", currentTime=2974.0, duration=3238.0), agora=0.0,
    )
    estado.registrar(
        evento(sessionId="ep2", currentTime=0.003, duration=2921.006), agora=1.0,
    )

    atual = estado.atual(agora=1.0)
    assert atual.sessionId == "ep2"
    assert atual.duration == pytest.approx(2921.006)
    assert atual.currentTime == pytest.approx(0.003)


def test_a_posicao_nao_passa_do_fim():
    """Batimento que parou de chegar não vira "assistiu além do fim"."""
    estado = EstadoDaPonte()
    estado.registrar(evento(currentTime=3230.0, duration=3238.0), agora=0.0)

    assert estado.atual(agora=20.0).posicao_agora(20.0) == pytest.approx(3238.0)


def test_a_vitrine_da_home_nao_vence_o_filme_pausado():
    """Medido em 25/08/2026 com o diagnóstico ao vivo:

        playing  pos=0.0/47.7    sem pageId    <- a vitrine da home
        paused   pos=222/8352    com pageId    <- Fight Club

    A vitrine da Netflix toca um trailer de quarenta segundos sozinha. Por
    "quem toca vence" ela ganhava do filme que a pessoa estava assistindo — que
    estava pausado justamente porque ela foi olhar outra coisa.
    """
    estado = EstadoDaPonte()
    estado.registrar(
        evento(sessionId="filme", playbackState="paused", currentTime=222.0,
               duration=8352.0, pageId="81234567", workTitle="Fight Club"),
        agora=0.0,
    )
    estado.registrar(
        evento(sessionId="vitrine", playbackState="playing", currentTime=0.0,
               duration=47.7),
        agora=1.0,
    )

    atual = estado.atual(agora=1.0)
    assert atual.sessionId == "filme"
    assert atual.workTitle == "Fight Club"


def test_entre_duas_com_identidade_quem_toca_ainda_vence():
    """A regra antiga continua valendo onde ela fazia sentido."""
    estado = EstadoDaPonte()
    estado.registrar(
        evento(sessionId="pausado", playbackState="paused", pageId="111"), agora=0.0,
    )
    estado.registrar(
        evento(sessionId="tocando", playbackState="playing", pageId="222"), agora=1.0,
    )

    assert estado.atual(agora=1.0).sessionId == "tocando"


def test_sem_identidade_em_nenhuma_o_desempate_e_o_de_antes():
    """Serviços sem adapter não têm `pageId`, e não podem perder por isso."""
    estado = EstadoDaPonte()
    estado.registrar(
        evento(sessionId="parada", provider="www.primevideo.com",
               playbackState="paused"), agora=0.0,
    )
    estado.registrar(
        evento(sessionId="tocando", provider="www.primevideo.com",
               playbackState="playing"), agora=1.0,
    )

    assert estado.atual(agora=1.0).sessionId == "tocando"


def test_o_fantasma_da_mesma_reproducao_e_substituido():
    """O observador troca de `sessionId` quando o `<video>` é trocado.

    A Netflix troca o elemento em mudança de qualidade, não só de episódio — e
    a sessão anterior continuava viva por cinco minutos descrevendo a MESMA
    coisa com um retrato velho.

    Medido em 26/08/2026: duas sessões com `duration=8352.218875`, uma sabendo
    o nome e a outra não. Elas alternavam o vencedor a cada batimento, o título
    piscava, e o gravador zerava o acumulado a cada piscada.
    """
    estado = EstadoDaPonte()
    estado.registrar(
        evento(sessionId="fantasma", currentTime=222.3, duration=8352.218875), agora=0.0,
    )
    estado.registrar(
        evento(sessionId="viva", currentTime=305.3, duration=8352.218875,
               workTitle="Fight Club"),
        agora=1.0,
    )

    vivas = estado.vivas(agora=1.0)
    assert len(vivas) == 1
    assert vivas[0].sessionId == "viva"


def test_duas_reproducoes_diferentes_nao_sao_fundidas():
    """O par: durações diferentes são obras diferentes, e as duas ficam."""
    estado = EstadoDaPonte()
    estado.registrar(evento(sessionId="uma", duration=3238.0), agora=0.0)
    estado.registrar(evento(sessionId="outra", duration=5000.0), agora=1.0)

    assert len(estado.vivas(agora=1.0)) == 2


def test_quem_sabe_nomear_desempata_antes_do_relogio():
    """Sem isto o vencedor alternava a cada batimento, e o título piscava."""
    estado = EstadoDaPonte()
    estado.registrar(
        evento(sessionId="sem-nome", duration=3238.0, playbackState="paused"),
        agora=0.0,
    )
    estado.registrar(
        evento(sessionId="com-nome", duration=5000.0, playbackState="paused",
               workTitle="Fight Club"),
        agora=1.0,
    )
    # E o "sem nome" fala por último, que era o critério que vencia antes.
    estado.registrar(
        evento(sessionId="sem-nome", duration=3238.0, playbackState="paused"),
        agora=2.0,
    )

    assert estado.atual(agora=2.0).sessionId == "com-nome"



# ── Uma aba tem UMA sessão ────────────────────────────────────────────────
#
# Medido no diagnóstico ao vivo em 26/08/2026, com UMA aba do Prime aberta:
#
#     tab=1826140783 PRIME_VIDEO pos=0.0    dur=None
#         documentTitle='Prime Video: Watch movies, TV shows, ...'
#     tab=1826140783 PRIME_VIDEO pos=1084.8 dur=1329.184
#         documentTitle='Prime Video: Batman: The Animated Series: Volume 3'
#
# A primeira é a página inicial, de antes de a pessoa abrir o episódio. Ela
# ficava viva por cinco minutos disputando com a atual, e o sintoma é uma
# reprodução antiga reaparecendo depois de já ter sido fechada ou trocada.
#
# `_esquecer_fantasmas` não a alcança: ela casa por serviço MAIS duração, e uma
# sessão que nunca chegou a ter duração não casa com nada.

class TestUmaSessaoPorAba:
    def test_a_sessao_nova_encerra_a_anterior_da_mesma_aba(self):
        estado = EstadoDaPonte()
        estado.registrar(
            evento(
                sessionId="a-pagina-inicial", provider="www.primevideo.com",
                currentTime=0.0, duration=None, tabId=1826140783,
                documentTitle="Prime Video: Watch movies, TV shows, sports, and live TV",
            ),
            agora=0.0,
        )
        estado.registrar(
            evento(
                sessionId="o-episodio", provider="www.primevideo.com",
                currentTime=1084.849, duration=1329.184, tabId=1826140783,
                documentTitle="Prime Video: Batman: The Animated Series: Volume 3",
            ),
            agora=1.0,
        )

        vivas = estado.vivas(agora=1.0)

        assert len(vivas) == 1
        assert vivas[0].sessionId == "o-episodio"

    def test_abas_DIFERENTES_convivem(self):
        """Duas abas tocando é estado legítimo, e quem arbitra é a Fase 15.

        Confundir "mesma aba" com "mesmo serviço" apagaria a segunda aba, e o
        desempate deixaria de existir por não haver mais o que desempatar.
        """
        estado = EstadoDaPonte()
        estado.registrar(
            evento(sessionId="uma", provider="www.primevideo.com", tabId=1),
            agora=0.0,
        )
        estado.registrar(
            evento(sessionId="outra", provider="www.primevideo.com", tabId=2, duration=999.0),
            agora=1.0,
        )

        assert len(estado.vivas(agora=1.0)) == 2

    def test_o_mesmo_sessionId_atualiza_em_vez_de_duplicar(self):
        """O caso comum: batimento seguinte da mesma reprodução."""
        estado = EstadoDaPonte()
        estado.registrar(evento(sessionId="s", tabId=7, currentTime=10.0), agora=0.0)
        estado.registrar(evento(sessionId="s", tabId=7, currentTime=20.0), agora=1.0)

        vivas = estado.vivas(agora=1.0)

        assert len(vivas) == 1
        assert vivas[0].currentTime == pytest.approx(20.0)

    def test_sem_tabId_nada_e_apagado(self):
        """Sem `tabId` não há origem a comparar.

        Ele vem do `sender` no service worker — o Chrome afirmando —, e uma
        mensagem que não passou por lá não o tem. Apagar por ausência jogaria
        fora sessões boas.
        """
        estado = EstadoDaPonte()
        estado.registrar(evento(sessionId="uma", tabId=None), agora=0.0)
        estado.registrar(evento(sessionId="outra", tabId=None, duration=999.0), agora=1.0)

        assert len(estado.vivas(agora=1.0)) == 2

    def test_a_aba_nova_de_OUTRO_servico_tambem_encerra(self):
        """A pessoa navegou do Prime para a Netflix na mesma aba.

        O `sessionId` troca porque a página troca, e a sessão do Prime naquela
        aba acabou — mesmo o serviço sendo outro.
        """
        estado = EstadoDaPonte()
        estado.registrar(
            evento(sessionId="prime", provider="www.primevideo.com", tabId=42),
            agora=0.0,
        )
        estado.registrar(
            evento(sessionId="netflix", provider="www.netflix.com", tabId=42),
            agora=1.0,
        )

        vivas = estado.vivas(agora=1.0)

        assert len(vivas) == 1
        assert vivas[0].platform == "NETFLIX"
