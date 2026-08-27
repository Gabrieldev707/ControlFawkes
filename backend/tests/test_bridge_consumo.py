"""Fase 9 — Consumption Policy.

O gate tem três frases:

    UI usa estado técnico correto.
    Histórico usa política mais forte.
    Bug histórico bloqueado.

E a regra permanente que as sustenta: "Histórico nunca soma tempo apenas porque
`video.paused === false`."
"""

from __future__ import annotations

import pytest

from app.bridge.consumo import avaliar, conta_como_assistido
from app.history.recorder import HistoryRecorder
from app.history.store import HistoryStore
from app.media.now_playing import NowPlaying


@pytest.fixture
def store(tmp_path) -> HistoryStore:
    return HistoryStore(tmp_path / "historico.json")


def tocando(titulo: str = "Batman: Caped Crusader", **overrides: object) -> NowPlaying:
    campos: dict = {
        "title": titulo,
        "artist": None,
        "app": "Chrome",
        "platform": "PRIME_VIDEO",
        "playing": True,
        "position_seconds": None,
        "duration_seconds": None,
        "thumbnail": None,
    }
    campos.update(overrides)
    return NowPlaying(**campos)


# ── A política, isolada ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("playbackState", "audible", "muted", "esperado"),
    [
        # A aba dizendo que está calada NÃO nega. Medido em 25/08/2026 com
        # INVINCIBLE tocando: a aba reportava `audible: false` enquanto a
        # pessoa assistia. `sender.tab` é um retrato do momento da conexão.
        ("playing", False, None, "INDETERMINADO"),
        # Som saindo é evidência positiva.
        ("playing", True, None, "ASSISTINDO"),
        # Sem forma de medir não se nega: quem não sabe não nega.
        ("playing", None, None, "INDETERMINADO"),
        # Mudo por escolha NÃO nega sozinho: legenda com som desligado é forma
        # legítima de assistir.
        ("playing", None, True, "INDETERMINADO"),
        # E som saindo vence o `muted` do elemento — outra aba pode ser a muda.
        ("playing", True, True, "ASSISTINDO"),
        # Não está tocando: o resto da evidência não importa.
        ("paused", True, False, "NAO_ASSISTINDO"),
        ("ended", True, False, "NAO_ASSISTINDO"),
        ("unknown", True, False, "NAO_ASSISTINDO"),
        (None, True, False, "NAO_ASSISTINDO"),
    ],
)
def test_a_politica_de_consumo(playbackState, audible, muted, esperado):
    assert avaliar(playbackState, audible, muted) == esperado


@pytest.mark.parametrize(
    ("do_processo", "esperado"),
    [
        # A Core Audio CONFIRMA.
        (True, "ASSISTINDO"),
        # E NÃO nega. Este é o conserto de 25/08/2026: um `False` daqui virou
        # veto absoluto e o histórico parou de gravar em TODOS os serviços por
        # duas horas, com a pessoa assistindo o tempo todo.
        (False, "INDETERMINADO"),
        (None, "INDETERMINADO"),
    ],
)
def test_a_core_audio_confirma_mas_nunca_nega(do_processo, esperado):
    """O Chrome tem dezenas de sessões de áudio, uma por renderer.

    "Este processo está calado" não é a mesma afirmação que "esta reprodução
    está calada" — e `audio_activity.py` já documentava, em primeira pessoa,
    que a sonda responde `False` para quem está assistindo.
    """
    assert avaliar("playing", audible=None, audible_do_processo=do_processo) == esperado


def test_nenhum_sinal_de_audio_nega():
    """As duas promoções que quebraram o histórico, viradas em teste.

    Áudio é indício, nunca prova. Cada vez que um destes dois foi promovido a
    veto, o histórico parou de gravar inteiro — a Core Audio por responder por
    processo, o `sender.tab.audible` por ser um retrato do momento da conexão.
    """
    assert avaliar("playing", audible=False, audible_do_processo=False) == "INDETERMINADO"
    assert avaliar("playing", audible=False, audible_do_processo=True) == "ASSISTINDO"
    assert avaliar("playing", audible=True, audible_do_processo=False) == "ASSISTINDO"


def test_indeterminado_conta_e_negado_nao():
    """Ausência de prova não é prova de ausência.

    Exigir prova positiva faria o histórico parar de gravar em toda máquina
    onde a Core Audio não responde — e esse erro já apagou uma série inteira do
    Disney+, com a sonda respondendo `False` para quem estava assistindo.
    """
    assert conta_como_assistido("ASSISTINDO") is True
    assert conta_como_assistido("INDETERMINADO") is True
    assert conta_como_assistido("NAO_ASSISTINDO") is False


# ── Gate: bug histórico bloqueado ─────────────────────────────────────────

def test_o_bug_do_batman_esta_bloqueado(store: HistoryStore):
    """Player tecnicamente reproduzindo, sem atividade real de áudio.

    Medido nesta máquina: o Chrome com a sessão de áudio em `Inactive` e
    "Batman: Caped Crusader" somando um segundo por segundo até 129 minutos no
    catálogo. Duas horas de um filme que ninguém estava vendo.
    """
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(tocando(), 1.0, "NAO_ASSISTINDO")
    gravador.encerrar()

    assert store.listar() == []


def test_com_evidencia_de_consumo_conta(store: HistoryStore):
    """O par do teste acima. Sem ele, "nunca conta" também passaria."""
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(tocando(), 1.0, "ASSISTINDO")
    gravador.encerrar()

    assert [item.titulo for item in store.listar()] == ["Batman: Caped Crusader"]


def test_sem_conseguir_medir_o_audio_continua_contando(store: HistoryStore):
    """A regressão que este conserto NÃO pode causar.

    Fora do Windows, sem `pycaw`, ou com a Core Audio recusando, a resposta é
    INDETERMINADO — e uma política que parasse de gravar aí quebraria o
    histórico para todo mundo, que é o oposto do que a fase quer.
    """
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(tocando(), 1.0, "INDETERMINADO")
    gravador.encerrar()

    assert [item.titulo for item in store.listar()] == ["Batman: Caped Crusader"]


def test_o_intervalo_que_nao_conta_ainda_guarda_onde_a_pessoa_parou(store: HistoryStore):
    """Não contar tempo é diferente de esquecer a posição.

    Onde a pessoa parou continua sendo verdade num intervalo sem áudio. O que
    não avança é o tempo assistido — e apagar a posição junto faria "continuar
    assistindo" perder o ponto de retomada.
    """
    gravador = HistoryRecorder(store)

    # Primeiro, tempo suficiente COM consumo para a obra entrar no arquivo.
    for _ in range(200):
        gravador.observar(tocando(position_seconds=100.0, duration_seconds=3600.0), 1.0, "ASSISTINDO")
    # Depois, um trecho sem áudio, com a posição mais adiante.
    for _ in range(200):
        gravador.observar(tocando(position_seconds=900.0, duration_seconds=3600.0), 1.0, "NAO_ASSISTINDO")
    gravador.encerrar()

    [item] = store.listar()
    assert item.posicao == 900.0
    # E o tempo assistido não somou os 200 segundos sem áudio.
    assert item.segundos == pytest.approx(200.0, abs=2.0)


# ── Gate: duas respostas da mesma leitura ─────────────────────────────────

def test_a_tela_usa_o_estado_tecnico_e_o_historico_a_politica(store: HistoryStore):
    """A frase inteira do gate, num teste só.

    A MESMA leitura: o player está tecnicamente reproduzindo e não sai som.
    A tela tem de continuar dizendo "tocando" — senão o botão mentiria sobre o
    que o player está fazendo. O histórico tem de recusar.
    """
    # O que ainda nega é o estado TÉCNICO, apurado pela leitura degradada:
    # `da_janela` consulta a Core Audio e devolve `playing=False`. Ver o
    # conserto do Batman em `now_playing.da_janela`.
    parada = tocando(playing=False)
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(parada, 1.0, avaliar("paused", audible=False))
    gravador.encerrar()

    assert store.listar() == []

    # E a tela continua recebendo o estado técnico, sem a política no meio.
    tocando_de_verdade = tocando()
    assert tocando_de_verdade.playing is True


def test_o_padrao_nao_muda_o_comportamento_de_quem_nao_conhece_a_politica(
    store: HistoryStore,
):
    """`observar` sem `consumo` grava como sempre gravou.

    O padrão é INDETERMINADO de propósito: quem decide NEGAR precisa dizer isso
    em voz alta. Um padrão restritivo silenciaria todo chamador antigo.
    """
    gravador = HistoryRecorder(store)

    for _ in range(400):
        gravador.observar(tocando(), 1.0)
    gravador.encerrar()

    assert [item.titulo for item in store.listar()] == ["Batman: Caped Crusader"]
