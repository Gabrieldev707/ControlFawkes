"""Paridade entre os serviços — o que cada um captura em segundo plano.

Medido em 26/08/2026, e a assimetria era real: só a Netflix funcionava com a
aba atrás, porque só ela tem adapter. Os outros dependiam do título da JANELA,
e a janela do Chrome publica o título da aba ATIVA — quem trocava de aba sumia
do próprio controle.

    servico        adapter   janela     aba de fundo (antes)
    NETFLIX        sim       obra       sim
    PRIME_VIDEO    -         obra       NÃO CAPTURA
    DISNEY_PLUS    -         obra       NÃO CAPTURA
    MAX            -         episodio   NÃO CAPTURA
    YOUTUBE        -         obra       NÃO CAPTURA

A extensão está DENTRO de cada aba e lê o `document.title` sempre. É a mesma
string que a janela publica, e o mesmo limpador a trata.
"""

from __future__ import annotations

import pytest

from app.bridge.estado import EstadoDaPonte
from app.bridge.eventos import validar
from app.history.recorder import HistoryRecorder
from app.history.store import SEGUNDOS_PARA_CONTAR, HistoryStore
from app.media.fusao import fundir_com_a_ponte


@pytest.fixture
def store(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


def ponte(provider: str, titulo: str, **extra: object) -> EstadoDaPonte:
    """A ponte com uma aba tocando — e SEM leitura nenhuma do Windows."""
    payload: dict = {
        "sessionId": "s1",
        "provider": provider,
        "playbackState": "playing",
        "currentTime": 100.0,
        "duration": 2880.0,
        "documentTitle": titulo,
    }
    payload.update(extra)
    estado = EstadoDaPonte()
    estado.registrar(
        validar({
            "protocolVersion": 1, "messageType": "POSITION_SYNC",
            "timestamp": 0.0, "payload": payload,
        }, agora=1000.0),
        agora=0.0,
    )
    return estado


# ── Cada serviço, com a aba em segundo plano e o Windows cego ─────────────

@pytest.mark.parametrize(
    ("provider", "titulo_da_aba", "nome", "e_obra"),
    [
        # O Prime Video põe o serviço na frente.
        ("www.primevideo.com", "Prime Video: Invincible", "Invincible", True),
        # O Disney+ põe atrás, com barra.
        ("www.disneyplus.com", "O Justiceiro | Disney+", "O Justiceiro", True),
        # O YouTube nomeia o vídeo, que é a obra dele.
        ("www.youtube.com", "CHEGUEI NA SÍRIA - YouTube", "CHEGUEI NA SÍRIA", True),
        # O Max nomeia o EPISÓDIO, sempre. O nome aparece, e NÃO vale como obra.
        ("play.hbomax.com", "⁨46 Long⁩ • HBO Max", "46 Long", False),
        # A Netflix pela aba também funciona, mesmo sem o adapter responder.
        ("www.netflix.com", "Duna - Netflix", "Duna", True),
    ],
)
def test_o_nome_chega_pela_aba_sem_a_janela(provider, titulo_da_aba, nome, e_obra):
    lida = fundir_com_a_ponte(None, ponte(provider, titulo_da_aba), agora=0.0)

    assert lida is not None
    assert lida.title == nome
    # `trustworthy` continua decidido pela MESMA tabela de capacidade: o Max
    # publica episódio, e episódio não é obra.
    assert lida.trustworthy is e_obra


def test_o_adapter_vence_o_titulo_da_aba():
    """Onde há adapter, ele manda: ele sabe separar obra de episódio."""
    estado = ponte(
        "www.netflix.com", "Breaking Bad - Netflix",
        workTitle="Breaking Bad", episodeNumber=1, episodeTitle="Pilot",
    )

    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    assert lida.title == "Breaking Bad"
    assert lida.episode == "E1 · Pilot"


def test_a_pagina_de_catalogo_nao_vira_obra():
    """O mesmo filtro de sempre, agora aplicado ao título da aba."""
    lida = fundir_com_a_ponte(None, ponte("www.netflix.com", "Netflix"), agora=0.0)

    # O cartão existe (há o que controlar), mas o nome não é uma obra.
    assert lida is not None
    assert lida.trustworthy is False


@pytest.mark.parametrize(
    "titulo",
    ["Home - Netflix", "Minha lista - Netflix", "play.hbomax.com", "   "],
)
def test_paginas_de_navegacao_nao_nomeiam_obra(titulo):
    lida = fundir_com_a_ponte(None, ponte("www.netflix.com", titulo), agora=0.0)

    assert lida is None or lida.trustworthy is False


def test_o_prime_video_finalmente_entra_no_historico(store: HistoryStore):
    """A prova de ponta a ponta do que faltava.

    Com a aba em segundo plano, a janela do Chrome mostra outra coisa e o
    Windows não sabe de nada. Antes disto, nada era gravado.
    """
    estado = ponte("www.primevideo.com", "Prime Video: Invincible")
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(fundir_com_a_ponte(None, estado, agora=0.0), 1.0, "ASSISTINDO")
    gravador.encerrar()

    [item] = store.listar()
    assert item.titulo == "Invincible"
    assert item.platform == "PRIME_VIDEO"


def test_o_max_continua_sem_inventar_obra_pela_aba(store: HistoryStore):
    """A regressão proibida: "46 Long" é episódio, e não vira título assistido."""
    estado = ponte("play.hbomax.com", "⁨46 Long⁩ • HBO Max")
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(fundir_com_a_ponte(None, estado, agora=0.0), 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []


# ── A primeira gravação ───────────────────────────────────────────────────

def test_a_primeira_gravacao_acontece_aos_90_segundos(store: HistoryStore):
    """`SEGUNDOS_PARA_CONTAR` promete 90, e a linha só aparecia aos 120.

    As duas condições valiam desde o começo, e `_nao_gravado` cresce junto com
    `_acumulado` — então a condição de "gravar DE NOVO" estava sendo usada como
    condição de "gravar". Trinta segundos de espera por nada, somados à recarga
    da tela.
    """
    estado = ponte("www.primevideo.com", "Prime Video: Invincible")
    gravador = HistoryRecorder(store)
    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    for _ in range(95):
        gravador.observar(lida, 1.0, "ASSISTINDO")

    # Sem `encerrar()`: a linha tem de estar no arquivo já.
    assert [i.titulo for i in store.listar()] == ["Invincible"]


def test_antes_do_piso_nada_e_gravado(store: HistoryStore):
    """O par: o piso continua de pé, senão cada troca de aba viraria linha.

    O nome deste teste dizia "90 segundos" e o número virou 30 em 26/08/2026 —
    ver `SEGUNDOS_PARA_CONTAR`. Um teste que carrega o valor no nome envelhece
    junto com ele e passa a mentir sobre o que prova; o que ele prova é que
    EXISTE um piso, não quanto ele vale.
    """
    estado = ponte("www.primevideo.com", "Prime Video: Invincible")
    gravador = HistoryRecorder(store)
    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    for _ in range(int(SEGUNDOS_PARA_CONTAR) - 5):
        gravador.observar(lida, 1.0, "ASSISTINDO")

    assert store.listar() == []


# ── O que substituiu o relógio ────────────────────────────────────────────
#
# `SEGUNDOS_PARA_CONTAR` caiu de 90 para 30 em 26/08/2026. O piso alto existia
# porque o RELÓGIO era a única defesa contra prévia de catálogo virar linha de
# histórico — a vitrine da home da Netflix toca uma prévia de uns quarenta
# segundos sozinha, e nada sabia distinguir isso de reprodução de verdade.
#
# A defesa mudou de natureza: agora é o ADAPTER que se recusa a nomear obra
# fora de uma página de reprodução, e essa recusa não depende de quanto tempo
# passou. Estes testes são o que prende essa afirmação — se um deles cair, o
# conserto NÃO é subir o piso de volta: é descobrir qual guarda deixou passar.

def test_a_vitrine_sem_nome_de_obra_nao_vira_historico(store: HistoryStore):
    """A prévia da home: a ponte fala, e o adapter não nomeia obra nenhuma.

    Sem `workTitle` sobra o título da aba, e "Netflix" é genérico — barrado
    antes de virar obra. Trezentos segundos, muito além do piso: o que impede
    a linha não é o tempo.
    """
    estado = ponte("www.netflix.com", "Netflix")
    gravador = HistoryRecorder(store)
    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    for _ in range(300):
        gravador.observar(lida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []


def test_o_episodio_do_MAX_continua_sem_virar_obra(store: HistoryStore):
    """A janela do Max publica o EPISÓDIO, e isso não muda com o piso baixo.

    Medido em 26/08/2026: `document.title` valia "⁨Trust Fall⁩ • HBO Max"
    enquanto a série era "Lanternas". `PLATAFORMAS_COM_OBRA_NA_JANELA` é o que
    impede "Trust Fall" de virar uma obra no histórico.
    """
    estado = ponte("play.hbomax.com", "⁨Trust Fall⁩ • HBO Max")
    gravador = HistoryRecorder(store)
    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    for _ in range(300):
        gravador.observar(lida, 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []


def test_com_o_adapter_nomeando_a_obra_entra_depressa(store: HistoryStore):
    """E o par: quando o adapter NOMEIA, a linha aparece logo depois do piso.

    É o ganho que o usuário pediu — "continuar assistindo" deixou de esperar
    minutos por uma obra que o sistema já sabia identificar.
    """
    estado = ponte(
        "play.hbomax.com", "⁨Trust Fall⁩ • HBO Max",
        workTitle="Lanternas", episodeTitle="Salto no Escuro",
        seasonNumber=1, episodeNumber=2,
    )
    gravador = HistoryRecorder(store)
    lida = fundir_com_a_ponte(None, estado, agora=0.0)

    for _ in range(int(SEGUNDOS_PARA_CONTAR) + 5):
        gravador.observar(lida, 1.0, "ASSISTINDO")

    # Sem `encerrar()`: a linha tem de estar no arquivo já.
    itens = store.listar()
    assert [i.titulo for i in itens] == ["Lanternas"]
    assert itens[0].como_obra()["episodio"] == "T1 E2"
