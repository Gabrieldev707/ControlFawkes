"""Fase 2 — os contratos, e as duas invariantes que eles travam.

Estes testes não verificam comportamento: verificam FORMA. Existem porque as
duas decisões da Fase 2 são fáceis de desfazer sem perceber — basta alguém
achar prático acrescentar um `confidence` ou usar `playbackState` para contar
tempo, e a arquitetura inteira volta ao que era.
"""

from __future__ import annotations

import pytest

from app.bridge.contratos import (
    EstadoDeReproducao,
    Fonte,
    MediaField,
    SessaoCanonica,
)


# ── Invariante 1: procedência, nunca confidence ───────────────────────────


def test_o_campo_carrega_a_fonte_e_nao_um_numero():
    campo = MediaField(value="Breaking Bad", source="provider-adapter", trustworthy=True)

    assert campo.value == "Breaking Bad"
    assert campo.source == "provider-adapter"
    assert campo.trustworthy is True


def test_nao_existe_confidence_no_contrato():
    """Critério de implementação incorreta nº 3 do Master Loop.

    Um `confidence` numérico não sai de lugar nenhum e faz a decisão do Merger
    virar emergente. Se alguém acrescentar o campo, este teste cai.
    """
    campos = set(MediaField.__dataclass_fields__)

    assert campos == {"value", "source", "trustworthy"}
    assert "confidence" not in campos


def test_valor_presente_sem_autoridade_nao_e_utilizavel():
    """O caso do Max, exatamente.

    A janela publica "46 Long" e isso É um título — do EPISÓDIO. O valor está
    certo; a afirmação "isto é a obra" é que seria falsa. Foi "tem valor, logo
    serve" que pôs nome de episódio no lugar do nome da obra no histórico.
    """
    campo = MediaField(value="46 Long", source="window-title", trustworthy=False)

    assert campo.value is not None
    assert campo.utilizavel is False


def test_autoridade_sem_valor_tambem_nao_e_utilizavel():
    campo = MediaField(value=None, source="provider-adapter", trustworthy=True)

    assert campo.utilizavel is False


def test_ausente_e_diferente_de_respondeu_que_nao_sabe():
    """Ninguém observou não é o mesmo que observou e não achou. A diferença
    decide se vale a pena perguntar a outra fonte."""
    ausente = MediaField.ausente()

    assert ausente.value is None
    assert ausente.source is None
    assert ausente.trustworthy is False


def test_o_campo_e_imutavel():
    """O Merger compõe uma sessão nova; ele não corrige campos no lugar.
    Mutar aqui esconderia de onde o valor final veio."""
    campo = MediaField(value=1.0, source="smtc", trustworthy=True)

    with pytest.raises(Exception):
        campo.value = 2.0  # type: ignore[misc]


# ── Invariante 2: três perguntas diferentes ───────────────────────────────


def test_playback_state_e_audible_sao_campos_separados():
    """O bug do Batman nasceu de fundir os dois.

    `video.paused === false` responde "o player está rodando". Aba muda, aba em
    segundo plano, janela esquecida: todas têm `paused === false`. Contar tempo
    com isso somou 129 minutos de um filme que ninguém via.
    """
    campos = set(SessaoCanonica.__annotations__)

    assert "playbackState" in campos
    assert "audible" in campos
    assert "muted" in campos


def test_consumption_state_nao_e_um_campo_da_sessao():
    """Ele é DERIVADO, e derivado no backend.

    Nenhuma fonte sozinha sabe responder "isto conta como assistido": a
    extensão vê uma aba, a SMTC vê uma sessão, a Core Audio vê um processo. Pôr
    `consumptionState` como campo convidaria alguém a preenchê-lo de uma fonte
    só — que é o defeito, com nome novo.
    """
    assert "consumptionState" not in SessaoCanonica.__annotations__


def test_ended_e_um_estado_e_nao_um_booleano_de_pausa():
    """"Acabou" e "pausado" são coisas diferentes para o histórico: um conta
    como visto até o fim, o outro entra em "continuar assistindo"."""
    estados = set(EstadoDeReproducao.__args__)

    assert estados == {"playing", "paused", "ended", "unknown"}


# ── A sessão canônica ─────────────────────────────────────────────────────


def test_a_sessao_vazia_tem_todos_os_campos_ausentes():
    """O Merger parte daqui e preenche campo a campo, em vez de montar um
    dicionário e torcer para não faltar chave."""
    sessao = SessaoCanonica.vazia()

    assert all(
        getattr(sessao, nome).source is None
        for nome in SessaoCanonica.__annotations__
    )
    assert sessao.workTitle.utilizavel is False


def test_a_sessao_sabe_dizer_de_onde_veio_cada_campo():
    """É o que transforma "o título está errado" em "o título veio da janela, e
    para a Netflix a janela não é autoridade para título"."""
    sessao = SessaoCanonica(
        **{
            **{n: MediaField.ausente() for n in SessaoCanonica.__annotations__},
            "workTitle": MediaField("Breaking Bad", "provider-adapter", True),
            "currentTime": MediaField(1284.0, "html-media-element", True),
            "playbackState": MediaField("playing", "html-media-element", True),
        },
    )

    procedencia = sessao.procedencia()

    assert procedencia["workTitle"] == "provider-adapter"
    assert procedencia["currentTime"] == "html-media-element"
    assert procedencia["duration"] is None


def test_todos_os_campos_da_fase_2_existem():
    """A lista do Master Loop, travada. Campo que sumir derruba este teste."""
    esperados = {
        "provider", "mediaType",
        "workTitle", "episodeTitle", "seasonNumber", "episodeNumber",
        "playbackState", "audible", "muted",
        "currentTime", "duration", "playbackRate",
    }

    assert set(SessaoCanonica.__annotations__) == esperados


def test_as_quatro_fontes_estao_declaradas():
    """Window Title entre elas: o critério de implementação incorreta nº 9 é
    ela desaparecer do pipeline durante a V1."""
    assert set(Fonte.__args__) == {
        "smtc", "window-title", "html-media-element", "provider-adapter",
    }
