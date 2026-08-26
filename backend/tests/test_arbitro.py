"""Fase 15 — o MediaSessionArbiter.

Cada teste aqui está preso a uma MEDIÇÃO, e não a uma intuição. O gate da Fase
14 proíbe congelar esta política antes dos dados, e os dados são
`data/bridge/abas.jsonl`: 1542 observações, 1526 com telemetria de aba, dos
cinco serviços, lidas em 26/08/2026.

O que a leitura produziu, e que está citado nos testes:

    instantes com 2+ ABAS distintas                    703
    destes, com 2+ TOCANDO                              18
    ACTIVE  aponta exatamente uma em 12; VÁRIAS em  6
    AUDIBLE aponta exatamente uma em  4; NENHUMA em 14
    aba ATIVA, tocando, com audible=False       187 de 276
    windowFocused presente em                          29%
    visible diverge de active em                416 abas
    pictureInPicture observado                           0 vezes
"""

from __future__ import annotations

import pytest

from app.bridge.arbitro import escolher, por_que
from app.bridge.estado import SessaoDaPonte


def sessao(**overrides: object) -> SessaoDaPonte:
    """Uma sessão da ponte, montada direto.

    Direto e não pelo `EstadoDaPonte`: ele encerra a sessão anterior da mesma
    aba, e alguns destes casos precisam montar exatamente isso.
    """
    campos: dict = {
        "sessionId": "s1", "tabId": 1, "windowId": 1, "platform": "NETFLIX",
        "playbackState": "playing", "currentTime": 100.0, "duration": 3238.0,
        "playbackRate": 1.0, "muted": False, "audible": None,
        "workTitle": "Uma Obra", "episodeTitle": None, "seasonNumber": None,
        "episodeNumber": None, "pageId": None,
        "adapterPosition": None, "adapterDuration": None, "documentTitle": None,
        "active": None, "windowFocused": None, "tabMuted": None,
        "pictureInPicture": None, "visible": None,
        "msDesdeUltimoPlay": None, "msDesdeUltimoEvento": None,
        "visto_em": 0.0, "posicao_em": 0.0,
    }
    campos.update(overrides)
    return SessaoDaPonte(**campos)


# ── O caso que reordenou tudo ─────────────────────────────────────────────

class TestIdentificadaVemAntesDeTocando:
    """Medido em 25/08/2026, no diagnóstico ao vivo:

        playing  pos=0,0/47,7   sem pageId, sem obra  <- a vitrine da home
        paused   pos=222/8352   com pageId, "Fight Club"

    A primeira versão deste árbitro punha "tocando" no topo e ressuscitava o
    bug: o cartão trocava Fight Club por um trailer de quarenta segundos.
    """

    def test_a_vitrine_nao_vence_o_filme_pausado(self):
        filme = sessao(
            sessionId="filme", tabId=1, playbackState="paused",
            workTitle="Fight Club", pageId="81234567",
        )
        vitrine = sessao(
            sessionId="vitrine", tabId=2, playbackState="playing",
            workTitle=None, pageId=None, visto_em=10.0,
        )

        assert escolher([filme, vitrine]).sessionId == "filme"
        assert por_que(filme, [vitrine]) == "identificada"

    def test_entre_duas_identificadas_quem_toca_vence(self):
        pausada = sessao(sessionId="pausada", tabId=1, playbackState="paused")
        tocando = sessao(sessionId="tocando", tabId=2, playbackState="playing")

        assert escolher([pausada, tocando]).sessionId == "tocando"
        assert por_que(tocando, [pausada]) == "tocando"

    def test_uma_nao_identificada_sozinha_ainda_vence(self):
        """Não identificada não é desclassificada — só perde de quem é."""
        anonima = sessao(sessionId="anonima", workTitle=None, pageId=None)

        assert escolher([anonima]).sessionId == "anonima"


# ── audible: promove, nunca rebaixa ───────────────────────────────────────

class TestAudivelNuncaNega:
    """`aba ATIVA, tocando, com audible=False: 187 de 276` — 68%.

    O mesmo defeito que a Fase 9 pagou com duas horas de histórico morto, e que
    `audio_activity.py` documenta como herdado. Terceira aparição, agora com
    número.
    """

    def test_audible_False_na_aba_ativa_nao_a_derruba(self):
        ativa = sessao(sessionId="ativa", tabId=1, active=True, audible=False)
        fundo = sessao(sessionId="fundo", tabId=2, active=False, audible=False)

        assert escolher([ativa, fundo]).sessionId == "ativa"

    def test_audible_True_promove_quando_o_resto_empata(self):
        muda = sessao(sessionId="muda", tabId=1, audible=False)
        soando = sessao(sessionId="soando", tabId=2, audible=True)

        assert escolher([muda, soando]).sessionId == "soando"
        assert por_que(soando, [muda]) == "audivel"

    def test_False_e_None_valem_o_MESMO(self):
        """`False` aqui significa "não sei", e não "não está tocando".

        Se valessem diferente, a aba que declara `False` cairia abaixo da que
        não declara nada — e 68% das abas ativas declaram `False`.
        """
        com_false = sessao(sessionId="com-false", tabId=1, audible=False, visto_em=1.0)
        sem_nada = sessao(sessionId="sem-nada", tabId=2, audible=None, visto_em=0.0)

        # Empatam em audível, então decide o último critério: a mais recente.
        assert escolher([com_false, sem_nada]).sessionId == "com-false"

    def test_audible_nao_vence_de_TOCANDO(self):
        """Uma aba pausada e audível não descreve o que está acontecendo."""
        pausada = sessao(sessionId="pausada", tabId=1, playbackState="paused", audible=True)
        tocando = sessao(sessionId="tocando", tabId=2, audible=False)

        assert escolher([pausada, tocando]).sessionId == "tocando"


# ── active, e o empate que ele produz ─────────────────────────────────────

class TestAbaAtiva:
    def test_a_aba_ativa_vence_a_de_fundo(self):
        fundo = sessao(sessionId="fundo", tabId=1, active=False)
        ativa = sessao(sessionId="ativa", tabId=2, active=True)

        assert escolher([fundo, ativa]).sessionId == "ativa"
        assert por_que(ativa, [fundo]) == "aba-ativa"

    def test_duas_abas_ativas_sao_duas_JANELAS(self):
        """Medido: `active` aponta VÁRIAS em 6 dos 18 instantes.

        Cada janela do Chrome tem a sua aba selecionada. Quem desempata é o
        foco da janela — e é para isto que ele existe na ordem.
        """
        uma = sessao(sessionId="uma", tabId=1, windowId=1, active=True, windowFocused=False)
        outra = sessao(sessionId="outra", tabId=2, windowId=2, active=True, windowFocused=True)

        assert escolher([uma, outra]).sessionId == "outra"
        assert por_que(outra, [uma]) == "janela-em-foco"

    def test_windowFocused_ausente_nao_desclassifica(self):
        """Presente em só 29% das abas. Exigi-lo derrubaria a maioria."""
        sem = sessao(sessionId="sem", tabId=1, active=True, windowFocused=None, visto_em=1.0)
        outra = sessao(sessionId="outra", tabId=2, active=False, windowFocused=True)

        # `active` decide antes do foco, e a que não declara foco continua lá.
        assert escolher([sem, outra]).sessionId == "sem"


# ── visible, que não é active ─────────────────────────────────────────────

def test_visivel_nao_e_sinonimo_de_ativa():
    """Divergem em 416 observações: uma aba ativa numa janela minimizada não
    está sendo desenhada."""
    invisivel = sessao(sessionId="invisivel", tabId=1, active=True, visible=False)
    visivel = sessao(sessionId="visivel", tabId=2, active=True, visible=True)

    assert escolher([invisivel, visivel]).sessionId == "visivel"
    assert por_que(visivel, [invisivel]) == "visivel"


# ── O desempate entre duas que insistem em tocar ──────────────────────────

class TestQuemMandouTocarPorUltimo:
    def test_o_play_mais_recente_vence(self):
        antiga = sessao(sessionId="antiga", tabId=1, msDesdeUltimoPlay=60_000.0)
        recente = sessao(sessionId="recente", tabId=2, msDesdeUltimoPlay=3_000.0)

        assert escolher([antiga, recente]).sessionId == "recente"
        assert por_que(recente, [antiga]) == "play-mais-recente"

    def test_sem_o_dado_nunca_vence_de_quem_tem(self):
        """Ausente vira -infinito: não declarar não pode ser vantagem."""
        sem = sessao(sessionId="sem", tabId=1, msDesdeUltimoPlay=None, visto_em=99.0)
        com = sessao(sessionId="com", tabId=2, msDesdeUltimoPlay=600_000.0)

        assert escolher([sem, com]).sessionId == "com"


# ── Determinismo: o gate pede "troca previsível" ──────────────────────────

class TestSemOscilacao:
    def test_a_mesma_lista_devolve_sempre_a_mesma(self):
        """Um empate que devolvesse ora uma ora outra faria o cartão piscar
        sem nada ter mudado na tela."""
        umas = [sessao(sessionId=f"s{i}", tabId=i) for i in range(1, 6)]

        escolhas = {escolher(list(reversed(umas))).sessionId for _ in range(20)}
        escolhas |= {escolher(umas).sessionId for _ in range(20)}

        assert len(escolhas) == 1

    def test_empate_total_decide_pelo_sessionId(self):
        """Duas sessões vistas no mesmo instante são possíveis."""
        a = sessao(sessionId="aaa", tabId=1, visto_em=5.0)
        b = sessao(sessionId="bbb", tabId=2, visto_em=5.0)

        assert escolher([a, b]).sessionId == "bbb"
        assert por_que(b, [a]) == "desempate-final"

    def test_lista_vazia_nao_inventa_sessao(self):
        assert escolher([]) is None


# ── Uma aba, uma sessão ───────────────────────────────────────────────────

def test_duas_sessoes_da_mesma_aba_nao_disputam_entre_si():
    """Contá-las duas vezes foi o que torceu o dataset da Fase 14 inteiro:
    477 instantes de "duas tocando" que eram 18."""
    fantasma = sessao(sessionId="fantasma", tabId=7, workTitle=None, pageId=None)
    viva = sessao(sessionId="viva", tabId=7, workTitle="Lanternas")

    assert escolher([fantasma, viva]).sessionId == "viva"


# ── PiP: a decisão que NÃO foi tomada ─────────────────────────────────────

class TestPictureInPicture:
    """Zero observações em 1526. Rankeá-lo seria inventar.

    Estes testes NÃO afirmam que o comportamento atual é o desejado — eles
    registram qual ele é, para a mudança futura ser visível quando o dado
    chegar. É o oposto de congelar a política: é datá-la.
    """

    def test_hoje_o_PiP_nao_tem_voz_contra_uma_aba_ativa(self):
        em_pip = sessao(sessionId="pip", tabId=1, active=False, pictureInPicture=True)
        ativa = sessao(sessionId="ativa", tabId=2, active=True, pictureInPicture=False)

        # O caso que o PiP deveria ganhar, e hoje perde. Ver a docstring de
        # `arbitro.py`: falta a observação real para decidir com dado.
        assert escolher([em_pip, ativa]).sessionId == "ativa"

    def test_sozinha_em_PiP_ela_vence(self):
        em_pip = sessao(sessionId="pip", tabId=1, active=False, pictureInPicture=True)
        parada = sessao(sessionId="parada", tabId=2, playbackState="paused", active=True)

        assert escolher([em_pip, parada]).sessionId == "pip"


# ── O caso comum, que é a esmagadora maioria ──────────────────────────────

def test_uma_aba_tocando_e_a_resposta_sem_disputa():
    """881 dos instantes têm exatamente uma tocando."""
    unica = sessao(sessionId="unica", tabId=1)

    assert escolher([unica]).sessionId == "unica"
    assert por_que(unica, []) == "unica"


@pytest.mark.parametrize("quantas", [2, 3, 8])
def test_a_escolha_nao_depende_da_ordem_da_lista(quantas: int):
    sessoes = [
        sessao(sessionId=f"s{i}", tabId=i, active=(i == 2), visto_em=float(i))
        for i in range(1, quantas + 1)
    ]

    assert escolher(sessoes).sessionId == "s2"
    assert escolher(list(reversed(sessoes))).sessionId == "s2"


# ── O gate: o histórico não pode somar duas sessões ───────────────────────

def test_trocar_de_aba_nao_soma_as_duas_no_historico(tmp_path):
    """O item do gate da Fase 15 que não é sobre o árbitro, e sim sobre o que
    ele causa.

    A pessoa assiste um filme numa aba, troca para outro noutra aba. São duas
    obras, com dois tempos. Se o árbitro trocasse de vencedor sem o gravador
    fechar a conta anterior, os dois tempos virariam uma linha só — e essa
    linha diria que a pessoa assistiu duas horas do segundo filme.
    """
    from app.bridge.estado import EstadoDaPonte
    from app.history.recorder import HistoryRecorder
    from app.history.store import HistoryStore
    from app.media.fusao import fundir_com_a_ponte

    estado = EstadoDaPonte()
    gravador = HistoryRecorder(HistoryStore(tmp_path / "h.json"))

    def bater(sessao_pronta: SessaoDaPonte, segundos: int) -> None:
        estado._sessoes[sessao_pronta.sessionId] = sessao_pronta
        lida = fundir_com_a_ponte(None, estado, agora=0.0)
        for _ in range(segundos):
            gravador.observar(lida, 1.0, "ASSISTINDO")

    primeira = sessao(
        sessionId="aba-1", tabId=1, platform="NETFLIX", active=True,
        workTitle="Duna", pageId="111", duration=9000.0,
    )
    bater(primeira, 60)

    # A pessoa troca de aba: a primeira deixa de estar ativa e pausa.
    estado._sessoes["aba-1"] = sessao(
        sessionId="aba-1", tabId=1, platform="NETFLIX", active=False,
        playbackState="paused", workTitle="Duna", pageId="111", duration=9000.0,
    )
    segunda = sessao(
        sessionId="aba-2", tabId=2, platform="NETFLIX", active=True,
        workTitle="Fight Club", pageId="222", duration=8352.0, visto_em=10.0,
    )
    bater(segunda, 60)
    gravador.encerrar()

    linhas = {i.titulo: i.segundos for i in gravador.store.listar()}

    assert set(linhas) == {"Duna", "Fight Club"}
    # Cada uma com o SEU tempo. Somadas, seriam 120 numa linha só.
    assert linhas["Duna"] == pytest.approx(60.0, abs=2)
    assert linhas["Fight Club"] == pytest.approx(60.0, abs=2)
